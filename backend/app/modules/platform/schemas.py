from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PlatformOverviewSummary(BaseModel):
    company_count: int
    active_tenant_count: int
    suspended_tenant_count: int
    archived_tenant_count: int
    subscription_count: int
    active_subscription_count: int
    trialing_subscription_count: int
    past_due_subscription_count: int
    cancelled_subscription_count: int
    expired_subscription_count: int


class PlatformPlanSummary(BaseModel):
    plan_id: UUID
    code: str
    name: str
    is_active: bool
    company_count: int
    active_subscription_count: int
    trialing_subscription_count: int
    past_due_subscription_count: int
    cancelled_subscription_count: int
    expired_subscription_count: int


class PlatformOpsSummary(BaseModel):
    total_integrations: int
    active_integrations: int
    queued_sync_runs: int
    running_sync_runs: int
    failed_sync_runs_24h: int
    partially_failed_sync_runs_24h: int
    successful_sync_runs_24h: int
    failed_sync_errors_24h: int


class PlatformQueueSummary(BaseModel):
    pending_notifications: int
    failed_notifications: int
    pending_domain_events: int
    failed_domain_events: int


class PlatformRecentFailure(BaseModel):
    sync_run_id: UUID
    company_id: UUID
    company_name: str
    company_slug: str
    integration_id: UUID
    integration_name: str
    sync_type: str
    status: str
    error_summary: str | None
    started_at: datetime | None
    finished_at: datetime | None


class PlatformOverviewResponse(BaseModel):
    generated_at: datetime
    summary: PlatformOverviewSummary
    plans: list[PlatformPlanSummary]
    ops: PlatformOpsSummary
    queues: PlatformQueueSummary
    recent_failures: list[PlatformRecentFailure]


class PlatformSubscriptionItem(BaseModel):
    subscription_id: UUID
    company_id: UUID
    company_name: str
    company_slug: str
    plan_id: UUID
    plan_code: str
    plan_name: str
    status: str
    created_at: datetime
    current_period_ends_at: datetime | None
    trial_ends_at: datetime | None


class PlatformBillingResponse(BaseModel):
    generated_at: datetime
    summary: PlatformOverviewSummary
    plans: list[PlatformPlanSummary]
    subscriptions: list[PlatformSubscriptionItem]
