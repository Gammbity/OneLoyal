from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.datetime import utc_now
from app.common.pagination import PaginationParams
from app.core.errors import NotFoundError, ValidationAppError
from app.modules.campaigns.models import Campaign, GiftTier
from app.modules.customers.models import Customer
from app.modules.progress.models import CustomerCampaignProgress
from app.modules.sales.models import (
    PaymentStatus,
    SaleDocumentKind,
    SaleDocumentStatus,
    SaleRecord,
)

CALCULATION_VERSION = 1
DEFAULT_CALCULATION_RULES = {
    "amount_basis": "gross",
    "include_cancelled": False,
    "include_deleted": False,
    "subtract_returns": True,
    "payment_rule": "all_valid_documents",
    "currency_mismatch_policy": "exclude",
}


@dataclass(frozen=True)
class TierResult:
    current_tier: GiftTier | None
    next_tier: GiftTier | None
    amount_left_minor: int
    progress_percent_basis_points: int
    no_tiers: bool = False


@dataclass(frozen=True)
class CampaignRecalculationStats:
    campaign_id: UUID
    recalculated_count: int
    skipped_count: int
    failed_count: int
    affected_customer_count: int


def _merged_rules(campaign: Campaign) -> dict:
    rules = {**DEFAULT_CALCULATION_RULES, **(campaign.rules_json or {})}
    if rules["amount_basis"] not in {"gross", "net", "paid"}:
        raise ValidationAppError("Unsupported amount_basis rule.")
    if rules["payment_rule"] not in {
        "all_valid_documents",
        "paid_only",
        "paid_amount_only",
    }:
        raise ValidationAppError("Unsupported payment_rule.")
    if rules["currency_mismatch_policy"] not in {"exclude", "fail"}:
        raise ValidationAppError("Unsupported currency_mismatch_policy.")
    return rules


def _empty_stats(rules: dict) -> dict:
    return {
        "included_records_count": 0,
        "excluded_cancelled_count": 0,
        "excluded_deleted_count": 0,
        "excluded_currency_mismatch_count": 0,
        "excluded_unpaid_count": 0,
        "excluded_returns_count": 0,
        "no_tiers": False,
        "amount_basis": rules["amount_basis"],
        "payment_rule": rules["payment_rule"],
        "currency_mismatch_policy": rules["currency_mismatch_policy"],
    }


def _basis_points(numerator: int, denominator: int) -> int:
    if denominator <= 0 or numerator <= 0:
        return 0
    value = (Decimal(numerator) * Decimal("10000") / Decimal(denominator)).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )
    return max(0, min(10000, int(value)))


def _amount_for_record(record: SaleRecord, rules: dict) -> int:
    if rules["payment_rule"] == "paid_amount_only":
        return record.paid_amount_minor or 0

    amount_basis = rules["amount_basis"]
    if amount_basis == "gross":
        return record.gross_amount_minor
    if amount_basis == "net":
        return record.net_amount_minor if record.net_amount_minor is not None else (
            record.gross_amount_minor
        )
    return record.paid_amount_minor or 0


def _signed_amount(record: SaleRecord, amount: int, rules: dict) -> int:
    if record.document_kind in {
        SaleDocumentKind.RETURN.value,
        SaleDocumentKind.REFUND.value,
    }:
        if not rules["subtract_returns"]:
            return 0
        return -abs(amount)
    return amount * record.amount_sign


def _calculate_tiers(total_amount_minor: int, tiers: list[GiftTier]) -> TierResult:
    if not tiers:
        return TierResult(
            current_tier=None,
            next_tier=None,
            amount_left_minor=0,
            progress_percent_basis_points=0,
            no_tiers=True,
        )

    current_tier: GiftTier | None = None
    next_tier: GiftTier | None = None
    for tier in tiers:
        if total_amount_minor >= tier.required_amount_minor:
            current_tier = tier
        elif next_tier is None:
            next_tier = tier
            break

    if current_tier is None:
        first_tier = tiers[0]
        return TierResult(
            current_tier=None,
            next_tier=first_tier,
            amount_left_minor=max(
                first_tier.required_amount_minor - total_amount_minor,
                0,
            ),
            progress_percent_basis_points=_basis_points(
                total_amount_minor,
                first_tier.required_amount_minor,
            ),
        )

    if next_tier is None:
        return TierResult(
            current_tier=current_tier,
            next_tier=None,
            amount_left_minor=0,
            progress_percent_basis_points=10000,
        )

    interval_amount = (
        next_tier.required_amount_minor - current_tier.required_amount_minor
    )
    interval_progress = total_amount_minor - current_tier.required_amount_minor
    return TierResult(
        current_tier=current_tier,
        next_tier=next_tier,
        amount_left_minor=max(next_tier.required_amount_minor - total_amount_minor, 0),
        progress_percent_basis_points=_basis_points(interval_progress, interval_amount),
    )


class ProgressService:
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

    async def _active_tiers(
        self,
        session: AsyncSession,
        campaign: Campaign,
    ) -> list[GiftTier]:
        result = await session.execute(
            select(GiftTier)
            .where(
                GiftTier.company_id == campaign.company_id,
                GiftTier.campaign_id == campaign.id,
                GiftTier.is_active.is_(True),
                GiftTier.deleted_at.is_(None),
            )
            .order_by(GiftTier.required_amount_minor.asc())
        )
        return list(result.scalars().all())

    async def _sale_records_for_customer(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign: Campaign,
        customer_id: UUID,
    ) -> list[SaleRecord]:
        result = await session.execute(
            select(SaleRecord).where(
                SaleRecord.company_id == company_id,
                SaleRecord.customer_id == customer_id,
                SaleRecord.effective_date >= campaign.start_date,
                SaleRecord.effective_date <= campaign.end_date,
                SaleRecord.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    def _calculate_total(
        self,
        *,
        campaign: Campaign,
        sale_records: list[SaleRecord],
        rules: dict,
    ) -> tuple[int, dict]:
        stats = _empty_stats(rules)
        total_amount_minor = 0
        for record in sale_records:
            if record.currency != campaign.currency:
                stats["excluded_currency_mismatch_count"] += 1
                if rules["currency_mismatch_policy"] == "fail":
                    raise ValidationAppError(
                        "Sale record currency does not match campaign currency.",
                        details={
                            "sale_record_id": str(record.id),
                            "sale_currency": record.currency,
                            "campaign_currency": campaign.currency,
                        },
                    )
                continue

            if (
                not rules["include_cancelled"]
                and record.document_status == SaleDocumentStatus.CANCELLED.value
            ):
                stats["excluded_cancelled_count"] += 1
                continue

            is_deleted_document = (
                record.document_status == SaleDocumentStatus.DELETED.value
                or record.is_deleted_in_source
            )
            if not rules["include_deleted"] and is_deleted_document:
                stats["excluded_deleted_count"] += 1
                continue

            is_return_or_refund = record.document_kind in {
                SaleDocumentKind.RETURN.value,
                SaleDocumentKind.REFUND.value,
            }
            if is_return_or_refund and not rules["subtract_returns"]:
                stats["excluded_returns_count"] += 1
                continue

            if (
                rules["payment_rule"] == "paid_only"
                and record.payment_status != PaymentStatus.PAID.value
            ):
                stats["excluded_unpaid_count"] += 1
                continue

            amount = _amount_for_record(record, rules)
            total_amount_minor += _signed_amount(record, amount, rules)
            stats["included_records_count"] += 1

        return max(total_amount_minor, 0), stats

    async def _upsert_progress(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign: Campaign,
        customer: Customer,
        total_amount_minor: int,
        tier_result: TierResult,
        stats: dict,
    ) -> CustomerCampaignProgress:
        result = await session.execute(
            select(CustomerCampaignProgress).where(
                CustomerCampaignProgress.company_id == company_id,
                CustomerCampaignProgress.campaign_id == campaign.id,
                CustomerCampaignProgress.customer_id == customer.id,
            )
        )
        progress = result.scalar_one_or_none()
        now = utc_now()
        stats["no_tiers"] = tier_result.no_tiers

        values = {
            "total_amount_minor": total_amount_minor,
            "currency": campaign.currency,
            "current_tier_id": tier_result.current_tier.id
            if tier_result.current_tier
            else None,
            "next_tier_id": tier_result.next_tier.id if tier_result.next_tier else None,
            "amount_left_minor": tier_result.amount_left_minor,
            "progress_percent_basis_points": tier_result.progress_percent_basis_points,
            "calculation_version": CALCULATION_VERSION,
            "stats_json": stats,
            "calculated_at": now,
        }
        if progress is None:
            progress = CustomerCampaignProgress(
                company_id=company_id,
                campaign_id=campaign.id,
                customer_id=customer.id,
                **values,
            )
            session.add(progress)
        else:
            for field, value in values.items():
                setattr(progress, field, value)

        progress.customer = customer
        progress.campaign = campaign
        progress.current_tier = tier_result.current_tier
        progress.next_tier = tier_result.next_tier
        await session.flush()
        return progress

    async def calculate_customer_progress(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
        customer_id: UUID,
    ) -> CustomerCampaignProgress:
        campaign = await self._get_campaign(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
        )
        customer = await self._get_customer(
            session,
            company_id=company_id,
            customer_id=customer_id,
        )
        rules = _merged_rules(campaign)
        tiers = await self._active_tiers(session, campaign)
        sale_records = await self._sale_records_for_customer(
            session,
            company_id=company_id,
            campaign=campaign,
            customer_id=customer_id,
        )
        total_amount_minor, stats = self._calculate_total(
            campaign=campaign,
            sale_records=sale_records,
            rules=rules,
        )
        tier_result = _calculate_tiers(total_amount_minor, tiers)
        return await self._upsert_progress(
            session,
            company_id=company_id,
            campaign=campaign,
            customer=customer,
            total_amount_minor=total_amount_minor,
            tier_result=tier_result,
            stats=stats,
        )

    async def _affected_customer_ids(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign: Campaign,
    ) -> list[UUID]:
        result = await session.execute(
            select(SaleRecord.customer_id)
            .where(
                SaleRecord.company_id == company_id,
                SaleRecord.effective_date >= campaign.start_date,
                SaleRecord.effective_date <= campaign.end_date,
                SaleRecord.deleted_at.is_(None),
            )
            .distinct()
        )
        return list(result.scalars().all())

    async def recalculate_campaign_progress(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
        chunk_size: int = 500,
    ) -> CampaignRecalculationStats:
        campaign = await self._get_campaign(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
        )
        customer_ids = await self._affected_customer_ids(
            session,
            company_id=company_id,
            campaign=campaign,
        )
        return await self.recalculate_affected_customers(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
            customer_ids=customer_ids,
            chunk_size=chunk_size,
        )

    async def recalculate_affected_customers(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
        customer_ids: list[UUID],
        chunk_size: int = 500,
    ) -> CampaignRecalculationStats:
        recalculated_count = 0
        failed_count = 0
        for offset in range(0, len(customer_ids), chunk_size):
            chunk = customer_ids[offset : offset + chunk_size]
            for customer_id in chunk:
                try:
                    await self.calculate_customer_progress(
                        session,
                        company_id=company_id,
                        campaign_id=campaign_id,
                        customer_id=customer_id,
                    )
                    recalculated_count += 1
                except Exception:
                    failed_count += 1
                    raise

        return CampaignRecalculationStats(
            campaign_id=campaign_id,
            recalculated_count=recalculated_count,
            skipped_count=0,
            failed_count=failed_count,
            affected_customer_count=len(customer_ids),
        )

    async def get_customer_progress(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
        customer_id: UUID,
    ) -> CustomerCampaignProgress:
        result = await session.execute(
            select(CustomerCampaignProgress)
            .options(
                selectinload(CustomerCampaignProgress.customer),
                selectinload(CustomerCampaignProgress.current_tier),
                selectinload(CustomerCampaignProgress.next_tier),
            )
            .where(
                CustomerCampaignProgress.company_id == company_id,
                CustomerCampaignProgress.campaign_id == campaign_id,
                CustomerCampaignProgress.customer_id == customer_id,
            )
        )
        progress = result.scalar_one_or_none()
        if progress is None:
            raise NotFoundError("Customer campaign progress not found.")
        return progress

    async def list_campaign_progress(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        campaign_id: UUID,
        pagination: PaginationParams,
        customer_id: UUID | None = None,
        current_tier_id: UUID | None = None,
        next_tier_id: UUID | None = None,
        min_total_amount_minor: int | None = None,
        max_total_amount_minor: int | None = None,
        search: str | None = None,
    ) -> tuple[list[CustomerCampaignProgress], int]:
        await self._get_campaign(
            session,
            company_id=company_id,
            campaign_id=campaign_id,
        )
        filters = [
            CustomerCampaignProgress.company_id == company_id,
            CustomerCampaignProgress.campaign_id == campaign_id,
        ]
        if customer_id is not None:
            filters.append(CustomerCampaignProgress.customer_id == customer_id)
        if current_tier_id is not None:
            filters.append(CustomerCampaignProgress.current_tier_id == current_tier_id)
        if next_tier_id is not None:
            filters.append(CustomerCampaignProgress.next_tier_id == next_tier_id)
        if min_total_amount_minor is not None:
            filters.append(
                CustomerCampaignProgress.total_amount_minor >= min_total_amount_minor
            )
        if max_total_amount_minor is not None:
            filters.append(
                CustomerCampaignProgress.total_amount_minor <= max_total_amount_minor
            )

        query = select(CustomerCampaignProgress).where(*filters)
        count_query = select(CustomerCampaignProgress.id).where(*filters)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.join(Customer).where(Customer.name.ilike(pattern))
            count_query = count_query.join(Customer).where(Customer.name.ilike(pattern))

        total_result = await session.execute(
            select(func.count()).select_from(count_query.subquery())
        )
        result = await session.execute(
            query.options(
                selectinload(CustomerCampaignProgress.customer),
                selectinload(CustomerCampaignProgress.current_tier),
                selectinload(CustomerCampaignProgress.next_tier),
            )
            .order_by(CustomerCampaignProgress.total_amount_minor.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        return list(result.scalars().all()), int(total_result.scalar_one())


progress_service = ProgressService()
