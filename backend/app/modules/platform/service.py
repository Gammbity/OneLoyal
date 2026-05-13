from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.datetime import utc_now
from app.modules.billing.models import CompanySubscription, Plan, SubscriptionStatus
from app.modules.companies.models import Company, CompanyStatus
from app.modules.events.models import DomainEvent, DomainEventStatus
from app.modules.integrations.models import Integration, IntegrationStatus
from app.modules.notifications.models import (
    NotificationEvent,
    NotificationEventStatus,
)
from app.modules.platform.schemas import (
    PlatformBillingResponse,
    PlatformOpsSummary,
    PlatformOverviewResponse,
    PlatformOverviewSummary,
    PlatformPlanSummary,
    PlatformQueueSummary,
    PlatformRecentFailure,
    PlatformSubscriptionItem,
)
from app.modules.sync.models import SyncError, SyncRun, SyncRunStatus


class PlatformService:
    async def get_overview(self, session: AsyncSession) -> PlatformOverviewResponse:
        generated_at = utc_now()
        return PlatformOverviewResponse(
            generated_at=generated_at,
            summary=await self._summary(session),
            plans=await self._plan_summaries(session),
            ops=await self._ops_summary(session, generated_at=generated_at),
            queues=await self._queue_summary(session),
            recent_failures=await self._recent_failures(session),
        )

    async def get_billing(self, session: AsyncSession) -> PlatformBillingResponse:
        generated_at = utc_now()
        return PlatformBillingResponse(
            generated_at=generated_at,
            summary=await self._summary(session),
            plans=await self._plan_summaries(session),
            subscriptions=await self._subscriptions(session),
        )

    async def _summary(self, session: AsyncSession) -> PlatformOverviewSummary:
        company_rows = await session.execute(
            select(Company.status, func.count(Company.id)).group_by(Company.status)
        )
        company_counts = {status: count for status, count in company_rows.all()}

        subscription_rows = await session.execute(
            select(
                CompanySubscription.status,
                func.count(CompanySubscription.id),
            ).group_by(
                CompanySubscription.status
            )
        )
        subscription_counts = {
            status: count for status, count in subscription_rows.all()
        }

        return PlatformOverviewSummary(
            company_count=sum(company_counts.values()),
            active_tenant_count=company_counts.get(CompanyStatus.ACTIVE.value, 0),
            suspended_tenant_count=company_counts.get(
                CompanyStatus.SUSPENDED.value, 0
            ),
            archived_tenant_count=company_counts.get(CompanyStatus.ARCHIVED.value, 0),
            subscription_count=sum(subscription_counts.values()),
            active_subscription_count=subscription_counts.get(
                SubscriptionStatus.ACTIVE.value, 0
            ),
            trialing_subscription_count=subscription_counts.get(
                SubscriptionStatus.TRIALING.value, 0
            ),
            past_due_subscription_count=subscription_counts.get(
                SubscriptionStatus.PAST_DUE.value, 0
            ),
            cancelled_subscription_count=subscription_counts.get(
                SubscriptionStatus.CANCELLED.value, 0
            ),
            expired_subscription_count=subscription_counts.get(
                SubscriptionStatus.EXPIRED.value, 0
            ),
        )

    async def _plan_summaries(self, session: AsyncSession) -> list[PlatformPlanSummary]:
        rows = await session.execute(
            select(
                Plan.id,
                Plan.code,
                Plan.name,
                Plan.is_active,
                CompanySubscription.status,
                func.count(CompanySubscription.id),
            )
            .outerjoin(CompanySubscription, CompanySubscription.plan_id == Plan.id)
            .group_by(
                Plan.id,
                Plan.code,
                Plan.name,
                Plan.is_active,
                CompanySubscription.status,
            )
            .order_by(Plan.name.asc())
        )

        plan_map: dict[str, PlatformPlanSummary] = {}
        for plan_id, code, name, is_active, status, count in rows.all():
            key = str(plan_id)
            if key not in plan_map:
                plan_map[key] = PlatformPlanSummary(
                    plan_id=plan_id,
                    code=code,
                    name=name,
                    is_active=is_active,
                    company_count=0,
                    active_subscription_count=0,
                    trialing_subscription_count=0,
                    past_due_subscription_count=0,
                    cancelled_subscription_count=0,
                    expired_subscription_count=0,
                )

            summary = plan_map[key]
            if status is None:
                continue
            summary.company_count += count
            if status == SubscriptionStatus.ACTIVE.value:
                summary.active_subscription_count += count
            elif status == SubscriptionStatus.TRIALING.value:
                summary.trialing_subscription_count += count
            elif status == SubscriptionStatus.PAST_DUE.value:
                summary.past_due_subscription_count += count
            elif status == SubscriptionStatus.CANCELLED.value:
                summary.cancelled_subscription_count += count
            elif status == SubscriptionStatus.EXPIRED.value:
                summary.expired_subscription_count += count

        return list(plan_map.values())

    async def _ops_summary(
        self,
        session: AsyncSession,
        *,
        generated_at,
    ) -> PlatformOpsSummary:
        since = generated_at - timedelta(hours=24)
        total_integrations = await session.scalar(
            select(func.count(Integration.id)).where(Integration.deleted_at.is_(None))
        )
        active_integrations = await session.scalar(
            select(func.count(Integration.id)).where(
                Integration.deleted_at.is_(None),
                Integration.status == IntegrationStatus.ACTIVE.value,
            )
        )
        current_sync_rows = await session.execute(
            select(SyncRun.status, func.count(SyncRun.id)).group_by(SyncRun.status)
        )
        current_sync_counts = {
            status: count for status, count in current_sync_rows.all()
        }
        recent_sync_rows = await session.execute(
            select(SyncRun.status, func.count(SyncRun.id))
            .where(SyncRun.created_at >= since)
            .group_by(SyncRun.status)
        )
        recent_sync_counts = {status: count for status, count in recent_sync_rows.all()}
        failed_errors = await session.scalar(
            select(func.count(SyncError.id)).where(SyncError.created_at >= since)
        )

        return PlatformOpsSummary(
            total_integrations=total_integrations or 0,
            active_integrations=active_integrations or 0,
            queued_sync_runs=current_sync_counts.get(SyncRunStatus.QUEUED.value, 0),
            running_sync_runs=current_sync_counts.get(SyncRunStatus.RUNNING.value, 0),
            failed_sync_runs_24h=recent_sync_counts.get(
                SyncRunStatus.FAILED.value, 0
            ),
            partially_failed_sync_runs_24h=recent_sync_counts.get(
                SyncRunStatus.PARTIALLY_FAILED.value, 0
            ),
            successful_sync_runs_24h=recent_sync_counts.get(
                SyncRunStatus.SUCCESS.value, 0
            ),
            failed_sync_errors_24h=failed_errors or 0,
        )

    async def _queue_summary(self, session: AsyncSession) -> PlatformQueueSummary:
        pending_notifications = await session.scalar(
            select(func.count(NotificationEvent.id)).where(
                NotificationEvent.status == NotificationEventStatus.PENDING.value
            )
        )
        failed_notifications = await session.scalar(
            select(func.count(NotificationEvent.id)).where(
                NotificationEvent.status == NotificationEventStatus.FAILED.value
            )
        )
        pending_events = await session.scalar(
            select(func.count(DomainEvent.id)).where(
                DomainEvent.status == DomainEventStatus.PENDING.value
            )
        )
        failed_events = await session.scalar(
            select(func.count(DomainEvent.id)).where(
                DomainEvent.status == DomainEventStatus.FAILED.value
            )
        )
        return PlatformQueueSummary(
            pending_notifications=pending_notifications or 0,
            failed_notifications=failed_notifications or 0,
            pending_domain_events=pending_events or 0,
            failed_domain_events=failed_events or 0,
        )

    async def _recent_failures(
        self,
        session: AsyncSession,
    ) -> list[PlatformRecentFailure]:
        rows = await session.execute(
            select(
                SyncRun.id,
                Company.id,
                Company.name,
                Company.slug,
                Integration.id,
                Integration.name,
                SyncRun.sync_type,
                SyncRun.status,
                SyncRun.error_summary,
                SyncRun.started_at,
                SyncRun.finished_at,
            )
            .join(Company, SyncRun.company_id == Company.id)
            .join(Integration, SyncRun.integration_id == Integration.id)
            .where(
                SyncRun.status.in_(
                    [
                        SyncRunStatus.FAILED.value,
                        SyncRunStatus.PARTIALLY_FAILED.value,
                    ]
                )
            )
            .order_by(func.coalesce(SyncRun.finished_at, SyncRun.updated_at).desc())
            .limit(10)
        )
        return [
            PlatformRecentFailure(
                sync_run_id=sync_run_id,
                company_id=company_id,
                company_name=company_name,
                company_slug=company_slug,
                integration_id=integration_id,
                integration_name=integration_name,
                sync_type=sync_type,
                status=status,
                error_summary=error_summary,
                started_at=started_at,
                finished_at=finished_at,
            )
            for (
                sync_run_id,
                company_id,
                company_name,
                company_slug,
                integration_id,
                integration_name,
                sync_type,
                status,
                error_summary,
                started_at,
                finished_at,
            ) in rows.all()
        ]

    async def _subscriptions(
        self,
        session: AsyncSession,
    ) -> list[PlatformSubscriptionItem]:
        rows = await session.execute(
            select(CompanySubscription, Company, Plan)
            .join(Company, CompanySubscription.company_id == Company.id)
            .join(Plan, CompanySubscription.plan_id == Plan.id)
            .order_by(CompanySubscription.created_at.desc())
        )
        return [
            PlatformSubscriptionItem(
                subscription_id=subscription.id,
                company_id=company.id,
                company_name=company.name,
                company_slug=company.slug,
                plan_id=plan.id,
                plan_code=plan.code,
                plan_name=plan.name,
                status=subscription.status,
                created_at=subscription.created_at,
                current_period_ends_at=subscription.current_period_ends_at,
                trial_ends_at=subscription.trial_ends_at,
            )
            for subscription, company, plan in rows.all()
        ]


platform_service = PlatformService()
