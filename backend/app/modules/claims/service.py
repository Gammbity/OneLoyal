from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.datetime import utc_now
from app.common.pagination import PaginationParams
from app.core.errors import ConflictError, NotFoundError
from app.modules.campaigns.models import Campaign, CampaignStatus, GiftTier
from app.modules.claims.models import (
    ACTIVE_REWARD_CLAIM_STATUSES,
    RewardClaim,
    RewardClaimStatus,
)
from app.modules.claims.schemas import (
    PortalRewardClaimCreateRequest,
    RewardClaimCreateRequest,
)
from app.modules.customers.models import Customer
from app.modules.progress.models import CustomerCampaignProgress


class RewardClaimService:
    async def _get_campaign(
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

    async def _get_tier(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
        gift_tier_id: UUID,
        lock: bool = False,
    ) -> GiftTier:
        query = select(GiftTier).where(
            GiftTier.id == gift_tier_id,
            GiftTier.company_id == company_id,
            GiftTier.campaign_id == campaign_id,
            GiftTier.deleted_at.is_(None),
            GiftTier.is_active.is_(True),
        )
        if lock:
            query = query.with_for_update()
        result = await session.execute(query)
        tier = result.scalar_one_or_none()
        if tier is None:
            raise NotFoundError("Gift tier not found.")
        return tier

    async def _get_claim(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        claim_id: UUID,
    ) -> RewardClaim:
        result = await session.execute(
            select(RewardClaim)
            .options(
                selectinload(RewardClaim.customer),
                selectinload(RewardClaim.campaign),
                selectinload(RewardClaim.gift_tier),
            )
            .where(
                RewardClaim.id == claim_id,
                RewardClaim.company_id == company_id,
                RewardClaim.deleted_at.is_(None),
            )
        )
        claim = result.scalar_one_or_none()
        if claim is None:
            raise NotFoundError("Reward claim not found.")
        return claim

    async def _ensure_claimable(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign: Campaign,
        customer_id: UUID,
        tier: GiftTier,
    ) -> None:
        if not campaign.allow_claims:
            raise ConflictError("Reward claims are disabled for this campaign.")
        if campaign.status not in {
            CampaignStatus.ACTIVE.value,
            CampaignStatus.COMPLETED.value,
        }:
            raise ConflictError(
                "Claims are allowed only for active or completed campaigns."
            )

        result = await session.execute(
            select(CustomerCampaignProgress).where(
                CustomerCampaignProgress.company_id == company_id,
                CustomerCampaignProgress.campaign_id == campaign.id,
                CustomerCampaignProgress.customer_id == customer_id,
            )
        )
        progress = result.scalar_one_or_none()
        if progress is None:
            raise ConflictError("Customer progress must be calculated before claiming.")
        if progress.total_amount_minor < tier.required_amount_minor:
            raise ConflictError("Customer has not reached this gift tier.")

        active_claim = await session.execute(
            select(RewardClaim.id).where(
                RewardClaim.company_id == company_id,
                RewardClaim.campaign_id == campaign.id,
                RewardClaim.customer_id == customer_id,
                RewardClaim.status.in_(ACTIVE_REWARD_CLAIM_STATUSES),
                RewardClaim.deleted_at.is_(None),
            )
        )
        if active_claim.scalar_one_or_none() is not None:
            raise ConflictError(
                "Customer already has an active claim for this campaign."
            )

    def _reserve_stock(self, tier: GiftTier) -> None:
        if tier.stock_tracking_mode == "none":
            return
        if tier.stock_tracking_mode == "strict":
            available_quantity = tier.available_quantity
            if available_quantity is None or available_quantity <= 0:
                raise ConflictError("Gift tier does not have available stock.")
        tier.reserved_quantity += 1

    def _release_reserved_stock(self, tier: GiftTier) -> None:
        if tier.stock_tracking_mode == "none":
            return
        if tier.reserved_quantity <= 0:
            raise ConflictError("Gift tier stock reservation is inconsistent.")
        tier.reserved_quantity -= 1

    def _fulfill_reserved_stock(self, tier: GiftTier) -> None:
        if tier.stock_tracking_mode == "none":
            return
        if tier.reserved_quantity <= 0:
            raise ConflictError("Gift tier stock reservation is inconsistent.")
        tier.reserved_quantity -= 1
        tier.fulfilled_quantity += 1

    async def create_claim(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        data: RewardClaimCreateRequest | PortalRewardClaimCreateRequest,
        customer_id: UUID | None = None,
        campaign_id: UUID | None = None,
    ) -> RewardClaim:
        claim_campaign_id = campaign_id or data.campaign_id
        claim_customer_id = customer_id or data.customer_id
        customer = await self._get_customer(
            session,
            company_id=company_id,
            customer_id=claim_customer_id,
        )
        campaign = await self._get_campaign(
            session,
            company_id=company_id,
            campaign_id=claim_campaign_id,
        )
        tier = await self._get_tier(
            session,
            company_id=company_id,
            campaign_id=claim_campaign_id,
            gift_tier_id=data.gift_tier_id,
        )
        await self._ensure_claimable(
            session,
            company_id=company_id,
            campaign=campaign,
            customer_id=claim_customer_id,
            tier=tier,
        )

        claim = RewardClaim(
            company_id=company_id,
            campaign_id=claim_campaign_id,
            customer_id=claim_customer_id,
            gift_tier_id=tier.id,
            status=RewardClaimStatus.PENDING.value,
            customer_comment=data.customer_comment,
        )
        claim.customer = customer
        claim.campaign = campaign
        claim.gift_tier = tier
        session.add(claim)
        await session.flush()
        return claim

    async def list_claims(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        pagination: PaginationParams,
        campaign_id: UUID | None = None,
        customer_id: UUID | None = None,
        gift_tier_id: UUID | None = None,
        status: str | None = None,
    ) -> tuple[list[RewardClaim], int]:
        filters = [
            RewardClaim.company_id == company_id,
            RewardClaim.deleted_at.is_(None),
        ]
        if campaign_id is not None:
            filters.append(RewardClaim.campaign_id == campaign_id)
        if customer_id is not None:
            filters.append(RewardClaim.customer_id == customer_id)
        if gift_tier_id is not None:
            filters.append(RewardClaim.gift_tier_id == gift_tier_id)
        if status is not None:
            filters.append(RewardClaim.status == status)

        query: Select[tuple[RewardClaim]] = select(RewardClaim).where(*filters)
        total_result = await session.execute(
            select(func.count()).select_from(
                select(RewardClaim.id).where(*filters).subquery()
            )
        )
        result = await session.execute(
            query.options(
                selectinload(RewardClaim.customer),
                selectinload(RewardClaim.campaign),
                selectinload(RewardClaim.gift_tier),
            )
            .order_by(RewardClaim.created_at.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        return list(result.scalars().all()), int(total_result.scalar_one())

    async def get_claim(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        claim_id: UUID,
    ) -> RewardClaim:
        return await self._get_claim(session, company_id=company_id, claim_id=claim_id)

    async def get_portal_claim(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        customer_id: UUID,
        claim_id: UUID,
    ) -> RewardClaim:
        claim = await self._get_claim(session, company_id=company_id, claim_id=claim_id)
        if claim.customer_id != customer_id:
            raise NotFoundError("Reward claim not found.")
        return claim

    async def list_portal_claims(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        customer_id: UUID,
    ) -> list[RewardClaim]:
        result = await session.execute(
            select(RewardClaim)
            .options(
                selectinload(RewardClaim.customer),
                selectinload(RewardClaim.campaign),
                selectinload(RewardClaim.gift_tier),
            )
            .where(
                RewardClaim.company_id == company_id,
                RewardClaim.customer_id == customer_id,
                RewardClaim.deleted_at.is_(None),
            )
            .order_by(RewardClaim.created_at.desc())
        )
        return list(result.scalars().all())

    async def approve_claim(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        claim_id: UUID,
        decided_by_user_id: UUID,
        admin_comment: str | None = None,
    ) -> RewardClaim:
        claim = await self._get_claim(session, company_id=company_id, claim_id=claim_id)
        if claim.status != RewardClaimStatus.PENDING.value:
            raise ConflictError("Only pending claims can be approved.")
        tier = await self._get_tier(
            session,
            company_id=company_id,
            campaign_id=claim.campaign_id,
            gift_tier_id=claim.gift_tier_id,
            lock=True,
        )
        self._reserve_stock(tier)
        claim.status = RewardClaimStatus.APPROVED.value
        claim.admin_comment = admin_comment
        claim.decided_by_user_id = decided_by_user_id
        claim.decided_at = utc_now()
        claim.gift_tier = tier
        await session.flush()
        return claim

    async def reject_claim(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        claim_id: UUID,
        decided_by_user_id: UUID,
        admin_comment: str | None = None,
    ) -> RewardClaim:
        claim = await self._get_claim(session, company_id=company_id, claim_id=claim_id)
        if claim.status not in {
            RewardClaimStatus.PENDING.value,
            RewardClaimStatus.APPROVED.value,
        }:
            raise ConflictError("Only pending or approved claims can be rejected.")
        if claim.status == RewardClaimStatus.APPROVED.value:
            tier = await self._get_tier(
                session,
                company_id=company_id,
                campaign_id=claim.campaign_id,
                gift_tier_id=claim.gift_tier_id,
                lock=True,
            )
            self._release_reserved_stock(tier)
            claim.gift_tier = tier
        claim.status = RewardClaimStatus.REJECTED.value
        claim.admin_comment = admin_comment
        claim.decided_by_user_id = decided_by_user_id
        claim.decided_at = utc_now()
        await session.flush()
        return claim

    async def fulfill_claim(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        claim_id: UUID,
        fulfilled_by_user_id: UUID,
        admin_comment: str | None = None,
    ) -> RewardClaim:
        claim = await self._get_claim(session, company_id=company_id, claim_id=claim_id)
        if claim.status != RewardClaimStatus.APPROVED.value:
            raise ConflictError("Only approved claims can be fulfilled.")
        tier = await self._get_tier(
            session,
            company_id=company_id,
            campaign_id=claim.campaign_id,
            gift_tier_id=claim.gift_tier_id,
            lock=True,
        )
        self._fulfill_reserved_stock(tier)
        claim.status = RewardClaimStatus.FULFILLED.value
        claim.admin_comment = admin_comment
        claim.fulfilled_by_user_id = fulfilled_by_user_id
        claim.fulfilled_at = utc_now()
        claim.gift_tier = tier
        await session.flush()
        return claim

    async def cancel_claim(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        claim_id: UUID,
        cancelled_by_user_id: UUID | None = None,
        customer_id: UUID | None = None,
        admin_comment: str | None = None,
    ) -> RewardClaim:
        claim = await self._get_claim(session, company_id=company_id, claim_id=claim_id)
        if customer_id is not None and claim.customer_id != customer_id:
            raise NotFoundError("Reward claim not found.")
        if claim.status not in {
            RewardClaimStatus.PENDING.value,
            RewardClaimStatus.APPROVED.value,
        }:
            raise ConflictError("Only pending or approved claims can be cancelled.")
        if customer_id is not None and claim.status != RewardClaimStatus.PENDING.value:
            raise ConflictError("Customers can cancel only pending claims.")
        if claim.status == RewardClaimStatus.APPROVED.value:
            tier = await self._get_tier(
                session,
                company_id=company_id,
                campaign_id=claim.campaign_id,
                gift_tier_id=claim.gift_tier_id,
                lock=True,
            )
            self._release_reserved_stock(tier)
            claim.gift_tier = tier
        claim.status = RewardClaimStatus.CANCELLED.value
        claim.admin_comment = admin_comment
        claim.cancelled_by_user_id = cancelled_by_user_id
        claim.cancelled_at = utc_now()
        await session.flush()
        return claim


reward_claim_service = RewardClaimService()
