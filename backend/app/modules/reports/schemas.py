from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, field_serializer


class PercentMixin(BaseModel):
    @field_serializer("progress_percent", check_fields=False)
    def serialize_progress_percent(self, value: Decimal) -> str:
        return f"{value:.2f}"


class CampaignReportSummary(BaseModel):
    campaign_id: UUID
    campaign_title: str
    campaign_status: str
    campaign_start_date: date
    campaign_end_date: date
    currency: str


class CampaignOverviewTierBreakdown(BaseModel):
    tier_id: UUID
    tier_title: str
    required_amount_minor: int
    customers_currently_at_tier: int
    claims_count: int
    fulfilled_count: int


class CampaignOverviewReport(CampaignReportSummary):
    total_customers_with_progress: int
    total_purchase_amount_minor: int
    average_purchase_amount_minor: int
    customers_reached_any_tier: int
    customers_reached_highest_tier: int
    total_active_claims: int
    total_fulfilled_claims: int
    gift_tier_breakdown: list[CampaignOverviewTierBreakdown]


class TopCustomerReportItem(PercentMixin):
    customer_id: UUID
    customer_name: str
    total_amount_minor: int
    current_tier_id: UUID | None
    current_tier_title: str | None
    next_tier_id: UUID | None
    next_tier_title: str | None
    amount_left_minor: int
    progress_percent: Decimal
    claim_status: str | None = None


class CloseToNextTierReportItem(PercentMixin):
    customer_id: UUID
    customer_name: str
    phone: str | None
    email: str | None
    total_amount_minor: int
    current_tier_title: str | None
    next_tier_title: str
    amount_left_minor: int
    progress_percent: Decimal


class GiftLiabilityTierItem(BaseModel):
    tier_id: UUID
    tier_title: str
    required_amount_minor: int
    customers_qualified_for_tier: int
    customers_currently_at_tier: int
    pending_claims: int
    approved_claims: int
    fulfilled_claims: int
    stock_quantity: int | None
    reserved_quantity: int
    fulfilled_quantity: int
    available_quantity: int | None


class GiftLiabilityReport(BaseModel):
    campaign: CampaignReportSummary
    total_qualified_customers: int
    total_claims: int
    total_pending_claims: int
    total_approved_claims: int
    total_fulfilled_claims: int
    tiers: list[GiftLiabilityTierItem]


class RewardClaimReportItem(BaseModel):
    claim_id: UUID
    campaign_id: UUID
    campaign_title: str
    customer_id: UUID
    customer_name: str
    gift_tier_id: UUID
    gift_tier_title: str
    status: str
    created_at: datetime
    decided_at: datetime | None
    fulfilled_at: datetime | None


class RewardClaimReportSummary(BaseModel):
    total: int
    pending: int
    approved: int
    rejected: int
    fulfilled: int
    cancelled: int


class RewardClaimsReport(BaseModel):
    items: list[RewardClaimReportItem]
    summary: RewardClaimReportSummary


class SyncHealthIntegrationItem(BaseModel):
    integration_id: UUID
    provider: str
    name: str
    status: str
    last_attempted_sync_at: datetime | None
    last_successful_sync_at: datetime | None
    next_sync_at: datetime | None
    recent_success_count: int
    recent_failed_count: int
    recent_partially_failed_count: int
    last_error_summary: str | None


class SyncHealthRecentRunItem(BaseModel):
    sync_run_id: UUID
    integration_id: UUID
    provider: str
    sync_type: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    stats_json: dict[str, Any]
    error_summary: str | None


class SyncHealthSummary(BaseModel):
    total_integrations: int
    active_integrations: int
    failed_runs: int
    partially_failed_runs: int
    successful_runs: int


class SyncHealthReport(BaseModel):
    integrations: list[SyncHealthIntegrationItem]
    recent_runs: list[SyncHealthRecentRunItem]
    summary: SyncHealthSummary


class SalesManagerPerformanceItem(BaseModel):
    user_id: UUID
    full_name: str
    email: str
    assigned_customer_count: int
    total_purchase_amount_minor: int
    customers_reached_any_tier: int
    customers_close_to_next_tier_count: int
    fulfilled_claims_count: int
