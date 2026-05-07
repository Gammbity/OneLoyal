from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.errors import NotFoundError, ValidationAppError
from app.modules.campaigns.models import Campaign, GiftTier
from app.modules.claims.models import RewardClaim, RewardClaimStatus
from app.modules.customers.models import Customer, CustomerAssignment
from app.modules.integrations.models import Integration, IntegrationStatus
from app.modules.progress.models import CustomerCampaignProgress
from app.modules.reports.schemas import (
    CampaignOverviewReport,
    CampaignOverviewTierBreakdown,
    CampaignReportSummary,
    CloseToNextTierReportItem,
    GiftLiabilityReport,
    GiftLiabilityTierItem,
    RewardClaimReportItem,
    RewardClaimReportSummary,
    RewardClaimsReport,
    SalesManagerPerformanceItem,
    SyncHealthIntegrationItem,
    SyncHealthRecentRunItem,
    SyncHealthReport,
    SyncHealthSummary,
    TopCustomerReportItem,
)
from app.modules.sync.models import SyncError, SyncRun, SyncRunStatus
from app.modules.users.models import User, UserRole


@dataclass(frozen=True)
class ReportViewer:
    user_id: UUID
    role: str


ACTIVE_CLAIM_STATUSES = {
    RewardClaimStatus.PENDING.value,
    RewardClaimStatus.APPROVED.value,
}


def _validate_date_range(date_from: date | None, date_to: date | None) -> None:
    if date_from is not None and date_to is not None and date_to < date_from:
        raise ValidationAppError(
            "date_to must be greater than or equal to date_from.",
            details={"field": "date_to"},
        )


def _start_of_day(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=UTC)


def _end_of_day(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=UTC)


def _progress_percent(basis_points: int) -> Decimal:
    return Decimal(basis_points) / Decimal("100")


def _threshold_basis_points(value: Decimal) -> int:
    return int(
        (value * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


def _is_sales_manager(viewer: ReportViewer) -> bool:
    return viewer.role == UserRole.SALES_MANAGER.value


def _assigned_customer_ids(company_id: UUID, sales_manager_user_id: UUID) -> Select:
    return select(CustomerAssignment.customer_id).where(
        CustomerAssignment.company_id == company_id,
        CustomerAssignment.sales_manager_user_id == sales_manager_user_id,
    )


def _progress_filters(
    *,
    company_id: UUID,
    campaign_id: UUID,
    viewer: ReportViewer,
) -> list:
    filters = [
        CustomerCampaignProgress.company_id == company_id,
        CustomerCampaignProgress.campaign_id == campaign_id,
    ]
    if _is_sales_manager(viewer):
        filters.append(
            CustomerCampaignProgress.customer_id.in_(
                _assigned_customer_ids(company_id, viewer.user_id)
            )
        )
    return filters


def _claim_filters(
    *,
    company_id: UUID,
    viewer: ReportViewer,
    campaign_id: UUID | None = None,
) -> list:
    filters = [
        RewardClaim.company_id == company_id,
        RewardClaim.deleted_at.is_(None),
    ]
    if campaign_id is not None:
        filters.append(RewardClaim.campaign_id == campaign_id)
    if _is_sales_manager(viewer):
        filters.append(
            RewardClaim.customer_id.in_(
                _assigned_customer_ids(company_id, viewer.user_id)
            )
        )
    return filters


class ReportsService:
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

    async def _get_integration(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        integration_id: UUID,
    ) -> Integration:
        result = await session.execute(
            select(Integration).where(
                Integration.id == integration_id,
                Integration.company_id == company_id,
                Integration.deleted_at.is_(None),
            )
        )
        integration = result.scalar_one_or_none()
        if integration is None:
            raise NotFoundError("Integration not found.")
        return integration

    async def _campaign_tiers(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
    ) -> list[GiftTier]:
        result = await session.execute(
            select(GiftTier)
            .where(
                GiftTier.company_id == company_id,
                GiftTier.campaign_id == campaign_id,
                GiftTier.deleted_at.is_(None),
                GiftTier.is_active.is_(True),
            )
            .order_by(GiftTier.required_amount_minor.asc(), GiftTier.sort_order.asc())
        )
        return list(result.scalars().all())

    async def _ensure_tier(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
        tier_id: UUID,
    ) -> None:
        result = await session.execute(
            select(GiftTier.id).where(
                GiftTier.id == tier_id,
                GiftTier.company_id == company_id,
                GiftTier.campaign_id == campaign_id,
                GiftTier.deleted_at.is_(None),
                GiftTier.is_active.is_(True),
            )
        )
        if result.scalar_one_or_none() is None:
            raise NotFoundError("Gift tier not found.")

    def _campaign_summary(self, campaign: Campaign) -> CampaignReportSummary:
        return CampaignReportSummary(
            campaign_id=campaign.id,
            campaign_title=campaign.title,
            campaign_status=campaign.status,
            campaign_start_date=campaign.start_date,
            campaign_end_date=campaign.end_date,
            currency=campaign.currency,
        )

    async def get_campaign_overview(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
        viewer: ReportViewer,
    ) -> CampaignOverviewReport:
        campaign = await self._get_campaign(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
        )
        tiers = await self._campaign_tiers(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
        )
        progress_filters = _progress_filters(
            company_id=company_id,
            campaign_id=campaign_id,
            viewer=viewer,
        )
        summary_result = await session.execute(
            select(
                func.count(CustomerCampaignProgress.id),
                func.coalesce(
                    func.sum(CustomerCampaignProgress.total_amount_minor),
                    0,
                ),
                func.count(CustomerCampaignProgress.current_tier_id),
            ).where(*progress_filters)
        )
        progress_count, total_amount, reached_any = summary_result.one()
        progress_count = int(progress_count or 0)
        total_amount = int(total_amount or 0)
        reached_any = int(reached_any or 0)

        highest_tier = tiers[-1] if tiers else None
        reached_highest = 0
        if highest_tier is not None:
            highest_result = await session.execute(
                select(func.count(CustomerCampaignProgress.id)).where(
                    *progress_filters,
                    CustomerCampaignProgress.current_tier_id == highest_tier.id,
                )
            )
            reached_highest = int(highest_result.scalar_one() or 0)

        current_rows = await session.execute(
            select(
                CustomerCampaignProgress.current_tier_id,
                func.count(CustomerCampaignProgress.id),
            )
            .where(
                *progress_filters,
                CustomerCampaignProgress.current_tier_id.is_not(None),
            )
            .group_by(CustomerCampaignProgress.current_tier_id)
        )
        current_counts = {
            tier_id: int(count) for tier_id, count in current_rows.all()
        }

        claim_filters = _claim_filters(
            company_id=company_id,
            campaign_id=campaign_id,
            viewer=viewer,
        )
        claim_rows = await session.execute(
            select(RewardClaim.gift_tier_id, RewardClaim.status, func.count())
            .where(*claim_filters)
            .group_by(RewardClaim.gift_tier_id, RewardClaim.status)
        )
        claim_counts: dict[UUID, dict[str, int]] = {}
        for tier_id, status, count in claim_rows.all():
            claim_counts.setdefault(tier_id, {})[status] = int(count)

        status_totals: dict[str, int] = {}
        for counts in claim_counts.values():
            for status, count in counts.items():
                status_totals[status] = status_totals.get(status, 0) + count

        return CampaignOverviewReport(
            **self._campaign_summary(campaign).model_dump(),
            total_customers_with_progress=progress_count,
            total_purchase_amount_minor=total_amount,
            average_purchase_amount_minor=(
                total_amount // progress_count if progress_count else 0
            ),
            customers_reached_any_tier=reached_any,
            customers_reached_highest_tier=reached_highest,
            total_active_claims=sum(
                status_totals.get(status, 0) for status in ACTIVE_CLAIM_STATUSES
            ),
            total_fulfilled_claims=status_totals.get(
                RewardClaimStatus.FULFILLED.value,
                0,
            ),
            gift_tier_breakdown=[
                CampaignOverviewTierBreakdown(
                    tier_id=tier.id,
                    tier_title=tier.title,
                    required_amount_minor=tier.required_amount_minor,
                    customers_currently_at_tier=current_counts.get(tier.id, 0),
                    claims_count=sum(claim_counts.get(tier.id, {}).values()),
                    fulfilled_count=claim_counts.get(tier.id, {}).get(
                        RewardClaimStatus.FULFILLED.value,
                        0,
                    ),
                )
                for tier in tiers
            ],
        )

    async def get_top_customers(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
        viewer: ReportViewer,
        limit: int,
        offset: int,
        min_amount: int | None = None,
        tier_id: UUID | None = None,
    ) -> list[TopCustomerReportItem]:
        await self._get_campaign(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
        )
        if tier_id is not None:
            await self._ensure_tier(
                session,
                company_id=company_id,
                campaign_id=campaign_id,
                tier_id=tier_id,
            )

        CurrentTier = aliased(GiftTier)
        NextTier = aliased(GiftTier)
        filters = [
            *_progress_filters(
                company_id=company_id,
                campaign_id=campaign_id,
                viewer=viewer,
            ),
            Customer.deleted_at.is_(None),
        ]
        if min_amount is not None:
            filters.append(CustomerCampaignProgress.total_amount_minor >= min_amount)
        if tier_id is not None:
            filters.append(CustomerCampaignProgress.current_tier_id == tier_id)

        result = await session.execute(
            select(
                CustomerCampaignProgress.customer_id,
                Customer.name,
                CustomerCampaignProgress.total_amount_minor,
                CustomerCampaignProgress.current_tier_id,
                CurrentTier.title,
                CustomerCampaignProgress.next_tier_id,
                NextTier.title,
                CustomerCampaignProgress.amount_left_minor,
                CustomerCampaignProgress.progress_percent_basis_points,
            )
            .join(Customer, Customer.id == CustomerCampaignProgress.customer_id)
            .outerjoin(
                CurrentTier,
                CurrentTier.id == CustomerCampaignProgress.current_tier_id,
            )
            .outerjoin(NextTier, NextTier.id == CustomerCampaignProgress.next_tier_id)
            .where(*filters)
            .order_by(
                CustomerCampaignProgress.total_amount_minor.desc(),
                Customer.name.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        rows = result.all()
        customer_ids = [row[0] for row in rows]
        latest_claim_status = await self._latest_claim_statuses(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
            customer_ids=customer_ids,
            viewer=viewer,
        )

        return [
            TopCustomerReportItem(
                customer_id=customer_id,
                customer_name=customer_name,
                total_amount_minor=int(total_amount_minor),
                current_tier_id=current_tier_id,
                current_tier_title=current_tier_title,
                next_tier_id=next_tier_id,
                next_tier_title=next_tier_title,
                amount_left_minor=int(amount_left_minor),
                progress_percent=_progress_percent(progress_basis_points),
                claim_status=latest_claim_status.get(customer_id),
            )
            for (
                customer_id,
                customer_name,
                total_amount_minor,
                current_tier_id,
                current_tier_title,
                next_tier_id,
                next_tier_title,
                amount_left_minor,
                progress_basis_points,
            ) in rows
        ]

    async def _latest_claim_statuses(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
        customer_ids: list[UUID],
        viewer: ReportViewer,
    ) -> dict[UUID, str]:
        if not customer_ids:
            return {}
        result = await session.execute(
            select(RewardClaim.customer_id, RewardClaim.status)
            .where(
                *_claim_filters(
                    company_id=company_id,
                    campaign_id=campaign_id,
                    viewer=viewer,
                ),
                RewardClaim.customer_id.in_(customer_ids),
            )
            .order_by(RewardClaim.customer_id.asc(), RewardClaim.created_at.desc())
        )
        statuses: dict[UUID, str] = {}
        for customer_id, status in result.all():
            statuses.setdefault(customer_id, status)
        return statuses

    async def get_close_to_next_tier(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
        viewer: ReportViewer,
        limit: int,
        offset: int,
        threshold_amount_minor: int | None = None,
        threshold_percent: Decimal | None = None,
    ) -> list[CloseToNextTierReportItem]:
        await self._get_campaign(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
        )
        if threshold_amount_minor is None and threshold_percent is None:
            threshold_percent = Decimal("80")

        CurrentTier = aliased(GiftTier)
        NextTier = aliased(GiftTier)
        filters = [
            *_progress_filters(
                company_id=company_id,
                campaign_id=campaign_id,
                viewer=viewer,
            ),
            Customer.deleted_at.is_(None),
            CustomerCampaignProgress.next_tier_id.is_not(None),
            CustomerCampaignProgress.amount_left_minor > 0,
        ]
        if threshold_amount_minor is not None:
            filters.append(
                CustomerCampaignProgress.amount_left_minor <= threshold_amount_minor
            )
        if threshold_percent is not None:
            filters.append(
                CustomerCampaignProgress.progress_percent_basis_points
                >= _threshold_basis_points(threshold_percent)
            )

        result = await session.execute(
            select(
                CustomerCampaignProgress.customer_id,
                Customer.name,
                Customer.phone,
                Customer.email,
                CustomerCampaignProgress.total_amount_minor,
                CurrentTier.title,
                NextTier.title,
                CustomerCampaignProgress.amount_left_minor,
                CustomerCampaignProgress.progress_percent_basis_points,
            )
            .join(Customer, Customer.id == CustomerCampaignProgress.customer_id)
            .outerjoin(
                CurrentTier,
                CurrentTier.id == CustomerCampaignProgress.current_tier_id,
            )
            .join(NextTier, NextTier.id == CustomerCampaignProgress.next_tier_id)
            .where(*filters)
            .order_by(
                CustomerCampaignProgress.amount_left_minor.asc(),
                Customer.name.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return [
            CloseToNextTierReportItem(
                customer_id=customer_id,
                customer_name=customer_name,
                phone=phone,
                email=email,
                total_amount_minor=int(total_amount_minor),
                current_tier_title=current_tier_title,
                next_tier_title=next_tier_title,
                amount_left_minor=int(amount_left_minor),
                progress_percent=_progress_percent(progress_basis_points),
            )
            for (
                customer_id,
                customer_name,
                phone,
                email,
                total_amount_minor,
                current_tier_title,
                next_tier_title,
                amount_left_minor,
                progress_basis_points,
            ) in result.all()
        ]

    async def get_gift_liability(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
        viewer: ReportViewer,
    ) -> GiftLiabilityReport:
        campaign = await self._get_campaign(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
        )
        tiers = await self._campaign_tiers(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
        )
        progress_filters = _progress_filters(
            company_id=company_id,
            campaign_id=campaign_id,
            viewer=viewer,
        )

        total_qualified_customers = 0
        if tiers:
            qualified_result = await session.execute(
                select(func.count(CustomerCampaignProgress.id)).where(
                    *progress_filters,
                    CustomerCampaignProgress.total_amount_minor
                    >= tiers[0].required_amount_minor,
                )
            )
            total_qualified_customers = int(qualified_result.scalar_one() or 0)

        currently_rows = await session.execute(
            select(
                CustomerCampaignProgress.current_tier_id,
                func.count(CustomerCampaignProgress.id),
            )
            .where(
                *progress_filters,
                CustomerCampaignProgress.current_tier_id.is_not(None),
            )
            .group_by(CustomerCampaignProgress.current_tier_id)
        )
        currently_counts = {
            tier_id: int(count) for tier_id, count in currently_rows.all()
        }

        qualified_counts = await self._qualified_counts_by_tier(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
            tiers=tiers,
            viewer=viewer,
        )

        claim_filters = _claim_filters(
            company_id=company_id,
            campaign_id=campaign_id,
            viewer=viewer,
        )
        claim_rows = await session.execute(
            select(RewardClaim.gift_tier_id, RewardClaim.status, func.count())
            .where(*claim_filters)
            .group_by(RewardClaim.gift_tier_id, RewardClaim.status)
        )
        claims_by_tier: dict[UUID, dict[str, int]] = {}
        status_totals: dict[str, int] = {}
        for tier_id, status, count in claim_rows.all():
            count = int(count)
            claims_by_tier.setdefault(tier_id, {})[status] = count
            status_totals[status] = status_totals.get(status, 0) + count

        return GiftLiabilityReport(
            campaign=self._campaign_summary(campaign),
            total_qualified_customers=total_qualified_customers,
            total_claims=sum(status_totals.values()),
            total_pending_claims=status_totals.get(RewardClaimStatus.PENDING.value, 0),
            total_approved_claims=status_totals.get(
                RewardClaimStatus.APPROVED.value,
                0,
            ),
            total_fulfilled_claims=status_totals.get(
                RewardClaimStatus.FULFILLED.value,
                0,
            ),
            tiers=[
                GiftLiabilityTierItem(
                    tier_id=tier.id,
                    tier_title=tier.title,
                    required_amount_minor=tier.required_amount_minor,
                    customers_qualified_for_tier=qualified_counts.get(tier.id, 0),
                    customers_currently_at_tier=currently_counts.get(tier.id, 0),
                    pending_claims=claims_by_tier.get(tier.id, {}).get(
                        RewardClaimStatus.PENDING.value,
                        0,
                    ),
                    approved_claims=claims_by_tier.get(tier.id, {}).get(
                        RewardClaimStatus.APPROVED.value,
                        0,
                    ),
                    fulfilled_claims=claims_by_tier.get(tier.id, {}).get(
                        RewardClaimStatus.FULFILLED.value,
                        0,
                    ),
                    stock_quantity=tier.stock_quantity,
                    reserved_quantity=tier.reserved_quantity,
                    fulfilled_quantity=tier.fulfilled_quantity,
                    available_quantity=tier.available_quantity,
                )
                for tier in tiers
            ],
        )

    async def _qualified_counts_by_tier(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
        tiers: list[GiftTier],
        viewer: ReportViewer,
    ) -> dict[UUID, int]:
        if not tiers:
            return {}
        progress_join_conditions = [
            CustomerCampaignProgress.company_id == company_id,
            CustomerCampaignProgress.campaign_id == campaign_id,
            CustomerCampaignProgress.total_amount_minor
            >= GiftTier.required_amount_minor,
        ]
        if _is_sales_manager(viewer):
            progress_join_conditions.append(
                CustomerCampaignProgress.customer_id.in_(
                    _assigned_customer_ids(company_id, viewer.user_id)
                )
            )
        result = await session.execute(
            select(GiftTier.id, func.count(CustomerCampaignProgress.id))
            .select_from(GiftTier)
            .outerjoin(
                CustomerCampaignProgress,
                and_(*progress_join_conditions),
            )
            .where(
                GiftTier.id.in_([tier.id for tier in tiers]),
                GiftTier.company_id == company_id,
                GiftTier.campaign_id == campaign_id,
                GiftTier.deleted_at.is_(None),
                GiftTier.is_active.is_(True),
            )
            .group_by(GiftTier.id)
        )
        return {tier_id: int(count) for tier_id, count in result.all()}

    async def get_reward_claims_report(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        viewer: ReportViewer,
        limit: int,
        offset: int,
        campaign_id: UUID | None = None,
        status: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> RewardClaimsReport:
        _validate_date_range(date_from, date_to)
        campaign: Campaign | None = None
        if campaign_id is not None:
            campaign = await self._get_campaign(
                session,
                company_id=company_id,
                campaign_id=campaign_id,
            )
        valid_statuses = {item.value for item in RewardClaimStatus}
        if status is not None and status not in valid_statuses:
            raise ValidationAppError(
                "Unsupported reward claim status.",
                details={"field": "status"},
            )

        filters = _claim_filters(
            company_id=company_id,
            campaign_id=campaign_id,
            viewer=viewer,
        )
        if status is not None:
            filters.append(RewardClaim.status == status)
        if date_from is None and date_to is None and campaign is not None:
            date_from = campaign.start_date
            date_to = campaign.end_date
        if date_from is not None:
            filters.append(RewardClaim.created_at >= _start_of_day(date_from))
        if date_to is not None:
            filters.append(RewardClaim.created_at <= _end_of_day(date_to))

        rows_result = await session.execute(
            select(RewardClaim, Campaign.title, Customer.name, GiftTier.title)
            .join(Campaign, Campaign.id == RewardClaim.campaign_id)
            .join(Customer, Customer.id == RewardClaim.customer_id)
            .join(GiftTier, GiftTier.id == RewardClaim.gift_tier_id)
            .where(*filters)
            .order_by(RewardClaim.created_at.desc(), RewardClaim.id.desc())
            .limit(limit)
            .offset(offset)
        )
        items = [
            RewardClaimReportItem(
                claim_id=claim.id,
                campaign_id=claim.campaign_id,
                campaign_title=campaign_title,
                customer_id=claim.customer_id,
                customer_name=customer_name,
                gift_tier_id=claim.gift_tier_id,
                gift_tier_title=gift_tier_title,
                status=claim.status,
                created_at=claim.created_at,
                decided_at=claim.decided_at,
                fulfilled_at=claim.fulfilled_at,
            )
            for claim, campaign_title, customer_name, gift_tier_title in (
                rows_result.all()
            )
        ]

        summary_rows = await session.execute(
            select(RewardClaim.status, func.count()).where(*filters).group_by(
                RewardClaim.status
            )
        )
        counts = {
            claim_status: int(count) for claim_status, count in summary_rows.all()
        }
        return RewardClaimsReport(
            items=items,
            summary=RewardClaimReportSummary(
                total=sum(counts.values()),
                pending=counts.get(RewardClaimStatus.PENDING.value, 0),
                approved=counts.get(RewardClaimStatus.APPROVED.value, 0),
                rejected=counts.get(RewardClaimStatus.REJECTED.value, 0),
                fulfilled=counts.get(RewardClaimStatus.FULFILLED.value, 0),
                cancelled=counts.get(RewardClaimStatus.CANCELLED.value, 0),
            ),
        )

    async def get_sync_health(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        limit: int,
        offset: int,
        integration_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> SyncHealthReport:
        _validate_date_range(date_from, date_to)
        if integration_id is not None:
            await self._get_integration(
                session,
                company_id=company_id,
                integration_id=integration_id,
            )

        integration_filters = [
            Integration.company_id == company_id,
            Integration.deleted_at.is_(None),
        ]
        if integration_id is not None:
            integration_filters.append(Integration.id == integration_id)
        integration_result = await session.execute(
            select(Integration)
            .where(*integration_filters)
            .order_by(Integration.created_at.desc())
        )
        integrations = list(integration_result.scalars().all())

        sync_filters = self._sync_run_filters(
            company_id=company_id,
            integration_id=integration_id,
            date_from=date_from,
            date_to=date_to,
        )
        recent_rows = await session.execute(
            select(SyncRun, Integration.provider)
            .join(Integration, Integration.id == SyncRun.integration_id)
            .where(*sync_filters)
            .order_by(func.coalesce(SyncRun.started_at, SyncRun.created_at).desc())
            .limit(limit)
            .offset(offset)
        )
        recent_runs = [
            SyncHealthRecentRunItem(
                sync_run_id=sync_run.id,
                integration_id=sync_run.integration_id,
                provider=provider,
                sync_type=sync_run.sync_type,
                status=sync_run.status,
                started_at=sync_run.started_at,
                finished_at=sync_run.finished_at,
                stats_json=sync_run.stats_json,
                error_summary=sync_run.error_summary,
            )
            for sync_run, provider in recent_rows.all()
        ]

        run_status_counts = await self._sync_status_counts(
            session,
            sync_filters=sync_filters,
        )
        integration_items = [
            await self._sync_health_integration_item(
                session,
                company_id=company_id,
                integration=integration,
                date_from=date_from,
                date_to=date_to,
            )
            for integration in integrations
        ]

        return SyncHealthReport(
            integrations=integration_items,
            recent_runs=recent_runs,
            summary=SyncHealthSummary(
                total_integrations=len(integrations),
                active_integrations=sum(
                    1
                    for integration in integrations
                    if integration.status == IntegrationStatus.ACTIVE.value
                ),
                failed_runs=run_status_counts.get(SyncRunStatus.FAILED.value, 0),
                partially_failed_runs=run_status_counts.get(
                    SyncRunStatus.PARTIALLY_FAILED.value,
                    0,
                ),
                successful_runs=run_status_counts.get(SyncRunStatus.SUCCESS.value, 0),
            ),
        )

    def _sync_run_filters(
        self,
        *,
        company_id: UUID,
        integration_id: UUID | None,
        date_from: date | None,
        date_to: date | None,
    ) -> list:
        filters = [SyncRun.company_id == company_id]
        if integration_id is not None:
            filters.append(SyncRun.integration_id == integration_id)
        run_time = func.coalesce(SyncRun.started_at, SyncRun.created_at)
        if date_from is not None:
            filters.append(run_time >= _start_of_day(date_from))
        if date_to is not None:
            filters.append(run_time <= _end_of_day(date_to))
        return filters

    async def _sync_status_counts(
        self,
        session: AsyncSession,
        *,
        sync_filters: list,
    ) -> dict[str, int]:
        result = await session.execute(
            select(SyncRun.status, func.count()).where(*sync_filters).group_by(
                SyncRun.status
            )
        )
        return {status: int(count) for status, count in result.all()}

    async def _sync_health_integration_item(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        integration: Integration,
        date_from: date | None,
        date_to: date | None,
    ) -> SyncHealthIntegrationItem:
        counts = await self._sync_status_counts(
            session,
            sync_filters=self._sync_run_filters(
                company_id=company_id,
                integration_id=integration.id,
                date_from=date_from,
                date_to=date_to,
            ),
        )
        last_error_summary = await self._last_error_summary(
            session,
            company_id=company_id,
            integration_id=integration.id,
        )
        return SyncHealthIntegrationItem(
            integration_id=integration.id,
            provider=integration.provider,
            name=integration.name,
            status=integration.status,
            last_attempted_sync_at=integration.last_attempted_sync_at,
            last_successful_sync_at=integration.last_successful_sync_at,
            next_sync_at=integration.next_sync_at,
            recent_success_count=counts.get(SyncRunStatus.SUCCESS.value, 0),
            recent_failed_count=counts.get(SyncRunStatus.FAILED.value, 0),
            recent_partially_failed_count=counts.get(
                SyncRunStatus.PARTIALLY_FAILED.value,
                0,
            ),
            last_error_summary=last_error_summary,
        )

    async def _last_error_summary(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        integration_id: UUID,
    ) -> str | None:
        result = await session.execute(
            select(SyncRun.error_summary)
            .where(
                SyncRun.company_id == company_id,
                SyncRun.integration_id == integration_id,
                SyncRun.status.in_(
                    {
                        SyncRunStatus.FAILED.value,
                        SyncRunStatus.PARTIALLY_FAILED.value,
                    }
                ),
                SyncRun.error_summary.is_not(None),
            )
            .order_by(func.coalesce(SyncRun.started_at, SyncRun.created_at).desc())
            .limit(1)
        )
        error_summary = result.scalar_one_or_none()
        if error_summary is not None:
            return error_summary

        error_result = await session.execute(
            select(SyncError.message)
            .join(SyncRun, SyncRun.id == SyncError.sync_run_id)
            .where(
                SyncRun.company_id == company_id,
                SyncRun.integration_id == integration_id,
            )
            .order_by(SyncError.created_at.desc())
            .limit(1)
        )
        return error_result.scalar_one_or_none()

    async def get_sales_manager_performance(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        viewer: ReportViewer,
        campaign_id: UUID | None = None,
        close_threshold_percent: Decimal = Decimal("80"),
    ) -> list[SalesManagerPerformanceItem]:
        if campaign_id is not None:
            await self._get_campaign(
                session,
                company_id=company_id,
                campaign_id=campaign_id,
            )
        filters = [
            User.company_id == company_id,
            User.role == UserRole.SALES_MANAGER.value,
        ]
        if _is_sales_manager(viewer):
            filters.append(User.id == viewer.user_id)
        result = await session.execute(
            select(User).where(*filters).order_by(User.full_name.asc())
        )
        managers = list(result.scalars().all())
        return [
            await self._sales_manager_performance_item(
                session,
                company_id=company_id,
                manager=manager,
                campaign_id=campaign_id,
                close_threshold_percent=close_threshold_percent,
            )
            for manager in managers
        ]

    async def _sales_manager_performance_item(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        manager: User,
        campaign_id: UUID | None,
        close_threshold_percent: Decimal,
    ) -> SalesManagerPerformanceItem:
        assigned_customers = _assigned_customer_ids(company_id, manager.id)
        assigned_count_result = await session.execute(
            select(func.count(CustomerAssignment.id)).where(
                CustomerAssignment.company_id == company_id,
                CustomerAssignment.sales_manager_user_id == manager.id,
            )
        )
        progress_filters = [
            CustomerCampaignProgress.company_id == company_id,
            CustomerCampaignProgress.customer_id.in_(assigned_customers),
        ]
        if campaign_id is not None:
            progress_filters.append(CustomerCampaignProgress.campaign_id == campaign_id)

        progress_result = await session.execute(
            select(
                func.coalesce(
                    func.sum(CustomerCampaignProgress.total_amount_minor),
                    0,
                )
            ).where(*progress_filters)
        )
        total_amount = progress_result.scalar_one()
        reached_result = await session.execute(
            select(func.count(func.distinct(CustomerCampaignProgress.customer_id))).where(
                *progress_filters,
                CustomerCampaignProgress.current_tier_id.is_not(None),
            )
        )
        close_result = await session.execute(
            select(func.count(func.distinct(CustomerCampaignProgress.customer_id))).where(
                *progress_filters,
                CustomerCampaignProgress.next_tier_id.is_not(None),
                CustomerCampaignProgress.amount_left_minor > 0,
                CustomerCampaignProgress.progress_percent_basis_points
                >= _threshold_basis_points(close_threshold_percent),
            )
        )

        claim_filters = [
            RewardClaim.company_id == company_id,
            RewardClaim.customer_id.in_(
                _assigned_customer_ids(company_id, manager.id)
            ),
            RewardClaim.status == RewardClaimStatus.FULFILLED.value,
            RewardClaim.deleted_at.is_(None),
        ]
        if campaign_id is not None:
            claim_filters.append(RewardClaim.campaign_id == campaign_id)
        fulfilled_result = await session.execute(
            select(func.count(RewardClaim.id)).where(*claim_filters)
        )

        return SalesManagerPerformanceItem(
            user_id=manager.id,
            full_name=manager.full_name,
            email=manager.email,
            assigned_customer_count=int(assigned_count_result.scalar_one() or 0),
            total_purchase_amount_minor=int(total_amount or 0),
            customers_reached_any_tier=int(reached_result.scalar_one() or 0),
            customers_close_to_next_tier_count=int(close_result.scalar_one() or 0),
            fulfilled_claims_count=int(fulfilled_result.scalar_one() or 0),
        )


reports_service = ReportsService()
