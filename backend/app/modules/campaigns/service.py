from datetime import date
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PaginationParams
from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.modules.campaigns.models import Campaign, CampaignStatus, GiftTier
from app.common.i18n import get_localized_value, ensure_i18n_defaults
from app.modules.campaigns.schemas import (
    CampaignCreateRequest,
    CampaignUpdateRequest,
    GiftTierCreateRequest,
    GiftTierUpdateRequest,
)
from app.modules.companies.models import Company, CompanySettings


def _normalize_currency(value: str) -> str:
    normalized = value.strip().upper()
    if len(normalized) != 3 or not normalized.isalpha():
        raise ValidationAppError(
            "Currency must be a 3-letter ISO currency code.",
            details={"field": "currency"},
        )
    return normalized


def _validate_date_range(start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise ValidationAppError(
            "Campaign end date must be greater than or equal to start date.",
            details={"field": "end_date"},
        )


def _ensure_campaign_editable(campaign: Campaign) -> None:
    if campaign.status == CampaignStatus.ARCHIVED.value:
        raise ConflictError("Archived campaigns cannot be edited.")
    if campaign.status == CampaignStatus.COMPLETED.value:
        raise ConflictError("Completed campaigns cannot be edited.")


class CampaignService:
    async def _get_company(self, session: AsyncSession, company_id: UUID) -> Company:
        company = await session.get(Company, company_id)
        if company is None:
            raise NotFoundError("Company not found.")
        return company

    async def _get_company_settings(
        self,
        session: AsyncSession,
        company_id: UUID,
    ) -> CompanySettings | None:
        result = await session.execute(
            select(CompanySettings).where(CompanySettings.company_id == company_id)
        )
        return result.scalar_one_or_none()

    async def create_campaign(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        data: CampaignCreateRequest,
    ) -> Campaign:
        company = await self._get_company(session, company_id)
        company_settings = await self._get_company_settings(session, company_id)
        _validate_date_range(data.start_date, data.end_date)

        if data.allow_claims is not None:
            allow_claims = data.allow_claims
        elif company_settings is not None:
            allow_claims = company_settings.reward_claim_enabled_default
        else:
            allow_claims = True

        campaign = Campaign(
            company_id=company_id,
            title=data.title.strip(),
            title_i18n=ensure_i18n_defaults(data.title.strip()),
            description=data.description,
            description_i18n=ensure_i18n_defaults(data.description),
            start_date=data.start_date,
            end_date=data.end_date,
            status=CampaignStatus.DRAFT.value,
            currency=_normalize_currency(data.currency or company.base_currency),
            rules_json=data.rules_json or {},
            visibility_settings_json=data.visibility_settings_json or {},
            allow_claims=allow_claims,
        )
        session.add(campaign)
        await session.flush()
        return campaign

    async def list_campaigns(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        pagination: PaginationParams,
        status: str | None = None,
        start_date_from: date | None = None,
        start_date_to: date | None = None,
        search: str | None = None,
    ) -> tuple[list[Campaign], int]:
        filters = [Campaign.company_id == company_id, Campaign.deleted_at.is_(None)]
        if status is not None:
            filters.append(Campaign.status == status)
        if start_date_from is not None:
            filters.append(Campaign.start_date >= start_date_from)
        if start_date_to is not None:
            filters.append(Campaign.start_date <= start_date_to)
        if search:
            filters.append(Campaign.title.ilike(f"%{search.strip()}%"))

        base_query: Select[tuple[Campaign]] = select(Campaign).where(*filters)
        total_result = await session.execute(
            select(func.count()).select_from(select(Campaign.id).where(*filters).subquery())
        )
        result = await session.execute(
            base_query.order_by(Campaign.created_at.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        return list(result.scalars().all()), int(total_result.scalar_one())

    async def get_campaign(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
    ) -> Campaign:
        result = await session.execute(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.company_id == company_id,
                Campaign.deleted_at.is_(None),
            )
        )
        campaign = result.scalar_one_or_none()
        if campaign is None:
            raise NotFoundError("Campaign not found.")
        return campaign

    async def update_campaign(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
        data: CampaignUpdateRequest,
    ) -> Campaign:
        campaign = await self.get_campaign(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
        )
        _ensure_campaign_editable(campaign)

        update_data = data.model_dump(exclude_unset=True)
        new_start = update_data.get("start_date", campaign.start_date)
        new_end = update_data.get("end_date", campaign.end_date)
        _validate_date_range(new_start, new_end)

        for field, value in update_data.items():
            if field.endswith("_json") and value is None:
                value = {}
            if field == "title" and value is not None:
                value = value.strip()
                # keep english default in title_i18n
                if getattr(campaign, "title_i18n", None) is None:
                    campaign.title_i18n = {}
                campaign.title_i18n["en"] = value
            if field == "description" and value is not None:
                if getattr(campaign, "description_i18n", None) is None:
                    campaign.description_i18n = {}
                campaign.description_i18n["en"] = value
            setattr(campaign, field, value)

        await session.flush()
        return campaign

    async def delete_campaign(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
    ) -> Campaign:
        campaign = await self.get_campaign(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
        )
        campaign.mark_deleted()
        await session.flush()
        return campaign

    async def _active_tiers_for_campaign(
        self,
        session: AsyncSession,
        campaign: Campaign,
    ) -> list[GiftTier]:
        result = await session.execute(
            select(GiftTier).where(
                GiftTier.campaign_id == campaign.id,
                GiftTier.company_id == campaign.company_id,
                GiftTier.deleted_at.is_(None),
                GiftTier.is_active.is_(True),
            )
        )
        return list(result.scalars().all())

    async def _validate_activation(
        self,
        session: AsyncSession,
        campaign: Campaign,
    ) -> None:
        _validate_date_range(campaign.start_date, campaign.end_date)
        tiers = await self._active_tiers_for_campaign(session, campaign)
        if not tiers:
            raise ConflictError(
                "Campaign cannot be activated without active gift tiers."
            )

        seen_amounts: set[int] = set()
        for tier in tiers:
            if tier.currency != campaign.currency:
                raise ConflictError("All gift tiers must match campaign currency.")
            if tier.required_amount_minor in seen_amounts:
                raise ConflictError(
                    "Gift tier required amounts must be unique inside a campaign."
                )
            seen_amounts.add(tier.required_amount_minor)

    async def activate_campaign(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
    ) -> Campaign:
        campaign = await self.get_campaign(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
        )
        if campaign.status == CampaignStatus.ARCHIVED.value:
            raise ConflictError("Archived campaigns cannot be activated.")
        if campaign.status not in {
            CampaignStatus.DRAFT.value,
            CampaignStatus.PAUSED.value,
        }:
            raise ConflictError("Campaign cannot be activated from its current status.")

        await self._validate_activation(session, campaign)
        campaign.status = CampaignStatus.ACTIVE.value
        await session.flush()
        return campaign

    async def pause_campaign(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
    ) -> Campaign:
        campaign = await self.get_campaign(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
        )
        if campaign.status != CampaignStatus.ACTIVE.value:
            raise ConflictError("Only active campaigns can be paused.")
        campaign.status = CampaignStatus.PAUSED.value
        await session.flush()
        return campaign

    async def complete_campaign(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
    ) -> Campaign:
        campaign = await self.get_campaign(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
        )
        if campaign.status not in {
            CampaignStatus.ACTIVE.value,
            CampaignStatus.PAUSED.value,
        }:
            raise ConflictError("Only active or paused campaigns can be completed.")
        campaign.status = CampaignStatus.COMPLETED.value
        await session.flush()
        return campaign

    async def archive_campaign(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
    ) -> Campaign:
        campaign = await self.get_campaign(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
        )
        if campaign.status not in {
            CampaignStatus.DRAFT.value,
            CampaignStatus.COMPLETED.value,
        }:
            raise ConflictError("Only draft or completed campaigns can be archived.")
        campaign.status = CampaignStatus.ARCHIVED.value
        await session.flush()
        return campaign


class GiftTierService:
    async def _ensure_campaign_editable(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
    ) -> Campaign:
        campaign = await campaign_service.get_campaign(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
        )
        _ensure_campaign_editable(campaign)
        return campaign

    async def _ensure_amount_available(
        self,
        session: AsyncSession,
        *,
        campaign_id: UUID,
        required_amount_minor: int,
        exclude_tier_id: UUID | None = None,
    ) -> None:
        filters = [
            GiftTier.campaign_id == campaign_id,
            GiftTier.required_amount_minor == required_amount_minor,
            GiftTier.deleted_at.is_(None),
        ]
        if exclude_tier_id is not None:
            filters.append(GiftTier.id != exclude_tier_id)

        result = await session.execute(select(GiftTier.id).where(*filters))
        if result.scalar_one_or_none() is not None:
            raise ConflictError(
                "Gift tier required amount already exists in this campaign.",
                details={"field": "required_amount_minor"},
            )

    async def _next_sort_order(
        self,
        session: AsyncSession,
        campaign_id: UUID,
    ) -> int:
        result = await session.execute(
            select(func.max(GiftTier.sort_order)).where(
                GiftTier.campaign_id == campaign_id,
                GiftTier.deleted_at.is_(None),
            )
        )
        max_sort_order = result.scalar_one_or_none()
        return 0 if max_sort_order is None else int(max_sort_order) + 1

    async def create_tier(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
        data: GiftTierCreateRequest,
    ) -> GiftTier:
        campaign = await self._ensure_campaign_editable(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
        )
        await self._ensure_amount_available(
            session,
            campaign_id=campaign_id,
            required_amount_minor=data.required_amount_minor,
        )

        # prefer explicit i18n maps if provided
        title_i18n = getattr(data, "title_i18n", None) or ensure_i18n_defaults(data.title.strip())
        description_i18n = getattr(data, "description_i18n", None) or ensure_i18n_defaults(data.description)
        tier = GiftTier(
            company_id=company_id,
            campaign_id=campaign_id,
            title=(data.title.strip() if data.title else (title_i18n.get("en") if title_i18n else "")),
            title_i18n=title_i18n,
            description=data.description,
            description_i18n=description_i18n,
            required_amount_minor=data.required_amount_minor,
            currency=campaign.currency,
            image_url=data.image_url,
            stock_tracking_mode=data.stock_tracking_mode.value,
            stock_quantity=data.stock_quantity,
            reserved_quantity=0,
            fulfilled_quantity=0,
            sort_order=await self._next_sort_order(session, campaign_id),
            is_active=data.is_active,
        )
        session.add(tier)
        await session.flush()
        return tier

    async def list_tiers(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
    ) -> list[GiftTier]:
        await campaign_service.get_campaign(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
        )
        result = await session.execute(
            select(GiftTier)
            .where(
                GiftTier.company_id == company_id,
                GiftTier.campaign_id == campaign_id,
                GiftTier.deleted_at.is_(None),
            )
            .order_by(GiftTier.required_amount_minor.asc(), GiftTier.sort_order.asc())
        )
        return list(result.scalars().all())

    async def get_tier(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
        tier_id: UUID,
    ) -> GiftTier:
        result = await session.execute(
            select(GiftTier).where(
                GiftTier.id == tier_id,
                GiftTier.company_id == company_id,
                GiftTier.campaign_id == campaign_id,
                GiftTier.deleted_at.is_(None),
            )
        )
        tier = result.scalar_one_or_none()
        if tier is None:
            raise NotFoundError("Gift tier not found.")
        return tier

    async def update_tier(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
        tier_id: UUID,
        data: GiftTierUpdateRequest,
    ) -> GiftTier:
        await self._ensure_campaign_editable(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
        )
        tier = await self.get_tier(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
            tier_id=tier_id,
        )

        update_data = data.model_dump(exclude_unset=True)
        if "required_amount_minor" in update_data:
            await self._ensure_amount_available(
                session,
                campaign_id=campaign_id,
                required_amount_minor=update_data["required_amount_minor"],
                exclude_tier_id=tier_id,
            )

        for field, value in update_data.items():
            if field == "title" and value is not None:
                value = value.strip()
                if getattr(tier, "title_i18n", None) is None:
                    tier.title_i18n = {}
                tier.title_i18n["en"] = value
            if field == "title_i18n" and value is not None:
                tier.title_i18n = value
            if field == "stock_tracking_mode" and value is not None:
                value = value.value
            setattr(tier, field, value)

        await session.flush()
        return tier

    async def delete_tier(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
        tier_id: UUID,
    ) -> GiftTier:
        await self._ensure_campaign_editable(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
        )
        tier = await self.get_tier(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
            tier_id=tier_id,
        )
        tier.is_active = False
        tier.mark_deleted()
        await session.flush()
        return tier

    async def reorder_tiers(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
        tier_ids: list[UUID],
    ) -> list[GiftTier]:
        await self._ensure_campaign_editable(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
        )
        tiers = await self.list_tiers(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
        )
        tiers_by_id = {tier.id: tier for tier in tiers}
        if set(tier_ids) != set(tiers_by_id):
            raise ValidationAppError(
                "Reorder request must include every active gift tier exactly once.",
                details={"field": "tier_ids"},
            )

        for index, tier_id in enumerate(tier_ids):
            tiers_by_id[tier_id].sort_order = index

        await session.flush()
        return [tiers_by_id[tier_id] for tier_id in tier_ids]


campaign_service = CampaignService()
gift_tier_service = GiftTierService()
