import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.datetime import ensure_timezone_aware, utc_now
from app.core.errors import NotFoundError, UnauthorizedError
from app.core.security import decode_token, generate_secure_token
from app.core.settings import get_settings
from app.modules.campaigns.models import Campaign, CampaignStatus, GiftTier
from app.modules.companies.models import Company
from app.modules.customers.models import Customer
from app.modules.portal.models import MagicLinkToken
from app.modules.portal.schemas import (
    MagicLinkCreateResponse,
    PortalProgressSnapshotResponse,
)
from app.modules.progress.models import CustomerCampaignProgress
from app.modules.sales.models import SaleRecord


@dataclass(frozen=True)
class PortalContext:
    company_id: UUID
    customer_id: UUID
    token_id: UUID
    customer: Customer
    company: Company
    magic_link_token: MagicLinkToken


def hash_magic_token(raw_token: str) -> str:
    settings = get_settings()
    return hmac.new(
        settings.secret_key.encode("utf-8"),
        raw_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _portal_url(raw_token: str) -> str | None:
    settings = get_settings()
    if not settings.portal_base_url:
        return None
    separator = "&" if "?" in settings.portal_base_url else "?"
    return f"{settings.portal_base_url}{separator}token={raw_token}"


class PortalService:
    async def _get_customer(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        customer_id: UUID,
    ) -> Customer:
        result = await session.execute(
            select(Customer).where(
                Customer.id == customer_id,
                Customer.company_id == company_id,
                Customer.deleted_at.is_(None),
            )
        )
        customer = result.scalar_one_or_none()
        if customer is None:
            raise NotFoundError("Customer not found.")
        return customer

    async def create_magic_link(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        customer_id: UUID,
        created_by_user_id: UUID,
    ) -> MagicLinkCreateResponse:
        await self._get_customer(
            session,
            company_id=company_id,
            customer_id=customer_id,
        )
        settings = get_settings()
        raw_token = generate_secure_token(48)
        expires_at = utc_now() + timedelta(days=settings.magic_link_default_expire_days)
        magic_link = MagicLinkToken(
            company_id=company_id,
            customer_id=customer_id,
            token_hash=hash_magic_token(raw_token),
            expires_at=expires_at,
            created_by_user_id=created_by_user_id,
        )
        session.add(magic_link)
        await session.flush()
        return MagicLinkCreateResponse(
            token_id=magic_link.id,
            raw_token=raw_token,
            expires_at=magic_link.expires_at,
            portal_url=_portal_url(raw_token),
        )

    async def list_magic_links(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        customer_id: UUID,
    ) -> list[MagicLinkToken]:
        await self._get_customer(
            session,
            company_id=company_id,
            customer_id=customer_id,
        )
        result = await session.execute(
            select(MagicLinkToken)
            .where(
                MagicLinkToken.company_id == company_id,
                MagicLinkToken.customer_id == customer_id,
            )
            .order_by(MagicLinkToken.created_at.desc())
        )
        return list(result.scalars().all())

    async def revoke_magic_link(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        customer_id: UUID,
        token_id: UUID,
    ) -> MagicLinkToken:
        await self._get_customer(
            session,
            company_id=company_id,
            customer_id=customer_id,
        )
        result = await session.execute(
            select(MagicLinkToken).where(
                MagicLinkToken.id == token_id,
                MagicLinkToken.company_id == company_id,
                MagicLinkToken.customer_id == customer_id,
            )
        )
        magic_link = result.scalar_one_or_none()
        if magic_link is None:
            raise NotFoundError("Magic link token not found.")
        if magic_link.revoked_at is None:
            magic_link.revoked_at = utc_now()
        await session.flush()
        return magic_link

    async def _load_magic_link_by_raw_token(
        self,
        session: AsyncSession,
        raw_token: str,
    ) -> MagicLinkToken:
        result = await session.execute(
            select(MagicLinkToken)
            .options(
                selectinload(MagicLinkToken.customer),
                selectinload(MagicLinkToken.company),
            )
            .where(MagicLinkToken.token_hash == hash_magic_token(raw_token))
        )
        magic_link = result.scalar_one_or_none()
        if magic_link is None:
            raise UnauthorizedError("Invalid portal token.")
        self._validate_magic_link(magic_link)
        if magic_link.customer.deleted_at is not None:
            raise UnauthorizedError("Portal customer is not available.")
        return magic_link

    def _validate_magic_link(self, magic_link: MagicLinkToken) -> None:
        now = utc_now()
        if magic_link.revoked_at is not None:
            raise UnauthorizedError("Portal token has been revoked.")
        if ensure_timezone_aware(magic_link.expires_at) <= now:
            raise UnauthorizedError("Portal token has expired.")

    def _create_portal_access_token(
        self,
        magic_link: MagicLinkToken,
    ) -> tuple[str, int]:
        settings = get_settings()
        now = datetime.now(UTC)
        expires_delta = timedelta(hours=settings.portal_access_token_expire_hours)
        expires_at = now + expires_delta
        claims = {
            "sub": str(magic_link.customer_id),
            "company_id": str(magic_link.company_id),
            "token_id": str(magic_link.id),
            "iat": now,
            "exp": expires_at,
            "token_type": "portal_access",
        }
        token = jwt.encode(
            claims,
            settings.secret_key,
            algorithm=settings.jwt_algorithm,
        )
        return token, int(expires_delta.total_seconds())

    async def create_portal_session(
        self,
        session: AsyncSession,
        *,
        raw_token: str,
    ) -> tuple[str, int, Customer, Company]:
        magic_link = await self._load_magic_link_by_raw_token(session, raw_token)
        now = utc_now()
        if magic_link.used_at is None:
            magic_link.used_at = now
        magic_link.last_used_at = now
        magic_link.use_count += 1
        portal_access_token, expires_in = self._create_portal_access_token(magic_link)
        await session.commit()
        return portal_access_token, expires_in, magic_link.customer, magic_link.company

    async def get_portal_context(
        self,
        session: AsyncSession,
        *,
        portal_access_token: str,
    ) -> PortalContext:
        payload = decode_token(portal_access_token)
        if payload.get("token_type") != "portal_access":
            raise UnauthorizedError("Invalid portal token type.")
        try:
            token_id = UUID(str(payload["token_id"]))
            company_id = UUID(str(payload["company_id"]))
            customer_id = UUID(str(payload["sub"]))
        except (KeyError, ValueError) as exc:
            raise UnauthorizedError("Invalid portal token payload.") from exc

        result = await session.execute(
            select(MagicLinkToken)
            .options(
                selectinload(MagicLinkToken.customer),
                selectinload(MagicLinkToken.company),
            )
            .where(
                MagicLinkToken.id == token_id,
                MagicLinkToken.company_id == company_id,
                MagicLinkToken.customer_id == customer_id,
            )
        )
        magic_link = result.scalar_one_or_none()
        if magic_link is None:
            raise UnauthorizedError("Portal token is no longer valid.")
        self._validate_magic_link(magic_link)
        if magic_link.customer.deleted_at is not None:
            raise UnauthorizedError("Portal customer is not available.")

        return PortalContext(
            company_id=company_id,
            customer_id=customer_id,
            token_id=token_id,
            customer=magic_link.customer,
            company=magic_link.company,
            magic_link_token=magic_link,
        )

    async def list_portal_campaigns(
        self,
        session: AsyncSession,
        *,
        context: PortalContext,
    ) -> list[Campaign]:
        today = utc_now().date()
        result = await session.execute(
            select(Campaign)
            .where(
                Campaign.company_id == context.company_id,
                Campaign.status == CampaignStatus.ACTIVE.value,
                Campaign.deleted_at.is_(None),
                Campaign.start_date <= today,
                Campaign.end_date >= today,
            )
            .order_by(Campaign.start_date.desc())
        )
        return list(result.scalars().all())

    async def get_portal_campaign(
        self,
        session: AsyncSession,
        *,
        context: PortalContext,
        campaign_id: UUID,
    ) -> Campaign:
        today = utc_now().date()
        result = await session.execute(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.company_id == context.company_id,
                Campaign.status == CampaignStatus.ACTIVE.value,
                Campaign.deleted_at.is_(None),
                Campaign.start_date <= today,
                Campaign.end_date >= today,
            )
        )
        campaign = result.scalar_one_or_none()
        if campaign is None:
            raise NotFoundError("Campaign not found.")
        return campaign

    async def list_campaign_tiers(
        self,
        session: AsyncSession,
        *,
        context: PortalContext,
        campaign_id: UUID,
    ) -> list[GiftTier]:
        result = await session.execute(
            select(GiftTier)
            .where(
                GiftTier.company_id == context.company_id,
                GiftTier.campaign_id == campaign_id,
                GiftTier.deleted_at.is_(None),
                GiftTier.is_active.is_(True),
            )
            .order_by(GiftTier.required_amount_minor.asc())
        )
        return list(result.scalars().all())

    async def get_progress_snapshot(
        self,
        session: AsyncSession,
        *,
        context: PortalContext,
        campaign: Campaign,
        gift_tiers: list[GiftTier],
    ) -> PortalProgressSnapshotResponse:
        result = await session.execute(
            select(CustomerCampaignProgress)
            .options(
                selectinload(CustomerCampaignProgress.current_tier),
                selectinload(CustomerCampaignProgress.next_tier),
            )
            .where(
                CustomerCampaignProgress.company_id == context.company_id,
                CustomerCampaignProgress.campaign_id == campaign.id,
                CustomerCampaignProgress.customer_id == context.customer_id,
            )
        )
        progress = result.scalar_one_or_none()
        if progress is not None:
            return PortalProgressSnapshotResponse(
                is_snapshot_available=True,
                total_amount_minor=progress.total_amount_minor,
                currency=progress.currency,
                current_tier_id=progress.current_tier_id,
                current_tier_title=progress.current_tier_title,
                next_tier_id=progress.next_tier_id,
                next_tier_title=progress.next_tier_title,
                amount_left_minor=progress.amount_left_minor,
                progress_percent=progress.progress_percent,
                progress_percent_basis_points=progress.progress_percent_basis_points,
                calculated_at=progress.calculated_at,
            )

        next_tier = gift_tiers[0] if gift_tiers else None
        return PortalProgressSnapshotResponse(
            is_snapshot_available=False,
            total_amount_minor=0,
            currency=campaign.currency,
            current_tier_id=None,
            current_tier_title=None,
            next_tier_id=next_tier.id if next_tier else None,
            next_tier_title=next_tier.title if next_tier else None,
            amount_left_minor=next_tier.required_amount_minor if next_tier else 0,
            progress_percent=Decimal("0.00"),
            progress_percent_basis_points=0,
            calculated_at=None,
        )

    async def list_purchase_history(
        self,
        session: AsyncSession,
        *,
        context: PortalContext,
        campaign: Campaign,
    ) -> list[SaleRecord]:
        result = await session.execute(
            select(SaleRecord)
            .where(
                SaleRecord.company_id == context.company_id,
                SaleRecord.customer_id == context.customer_id,
                SaleRecord.effective_date >= campaign.start_date,
                SaleRecord.effective_date <= campaign.end_date,
                SaleRecord.deleted_at.is_(None),
            )
            .order_by(SaleRecord.effective_date.desc())
        )
        return list(result.scalars().all())


portal_service = PortalService()
