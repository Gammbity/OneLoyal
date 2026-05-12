import logging
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.datetime import utc_now
from app.core.settings import get_settings
from app.modules.events.models import DomainEvent, DomainEventStatus
from app.modules.integrations.models import Integration, IntegrationStatus
from app.modules.notifications.models import (
    NotificationEvent,
    NotificationEventStatus,
)
from app.modules.ops.schemas import (
    OpsStatusResponse,
    RecoverNotificationsResponse,
    RecoverStuckSyncsResponse,
)
from app.modules.sync.models import SyncError, SyncRun, SyncRunStatus

logger = logging.getLogger(__name__)
settings = get_settings()


class OpsService:
    async def get_status(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
    ) -> OpsStatusResponse:
        now = utc_now()
        queued_timeout = now - timedelta(minutes=settings.sync_queued_timeout_minutes)
        running_timeout = now - timedelta(minutes=settings.sync_running_timeout_minutes)

        # 1. Sync Runs Stats
        sync_status_counts = await session.execute(
            select(SyncRun.status, func.count(SyncRun.id))
            .where(SyncRun.company_id == company_id)
            .group_by(SyncRun.status)
        )
        sync_runs_dict = {status: count for status, count in sync_status_counts}

        # 2. Stuck Sync Counts
        stuck_queued = await session.scalar(
            select(func.count(SyncRun.id)).where(
                SyncRun.company_id == company_id,
                SyncRun.status == SyncRunStatus.QUEUED.value,
                SyncRun.created_at < queued_timeout,
            )
        )
        stuck_running = await session.scalar(
            select(func.count(SyncRun.id)).where(
                SyncRun.company_id == company_id,
                SyncRun.status == SyncRunStatus.RUNNING.value,
                SyncRun.started_at < running_timeout,
            )
        )

        # 3. Notification Stats
        pending_notifs = await session.scalar(
            select(func.count(NotificationEvent.id)).where(
                NotificationEvent.company_id == company_id,
                NotificationEvent.status == NotificationEventStatus.PENDING.value,
            )
        )
        failed_notifs = await session.scalar(
            select(func.count(NotificationEvent.id)).where(
                NotificationEvent.company_id == company_id,
                NotificationEvent.status == NotificationEventStatus.FAILED.value,
            )
        )

        # 4. Domain Event Stats
        pending_events = await session.scalar(
            select(func.count(DomainEvent.id)).where(
                DomainEvent.company_id == company_id,
                DomainEvent.status == DomainEventStatus.PENDING.value,
            )
        )
        failed_events = await session.scalar(
            select(func.count(DomainEvent.id)).where(
                DomainEvent.company_id == company_id,
                DomainEvent.status == DomainEventStatus.FAILED.value,
            )
        )

        # 5. Sync Errors
        recent_errors = await session.scalar(
            select(func.count(SyncError.id)).where(
                SyncError.company_id == company_id,
                SyncError.created_at > now - timedelta(hours=24),
            )
        )

        # 6. Integration Stats
        active_integrations = await session.scalar(
            select(func.count(Integration.id)).where(
                Integration.company_id == company_id,
                Integration.status == IntegrationStatus.ACTIVE.value,
                Integration.deleted_at.is_(None),
            )
        )
        # We check settings_json for scheduled_sync_enabled
        # This is a bit slow with JSON in SQL, but for status it's fine
        scheduled_integrations = await session.scalar(
            select(func.count(Integration.id)).where(
                Integration.company_id == company_id,
                Integration.status == IntegrationStatus.ACTIVE.value,
                Integration.deleted_at.is_(None),
                Integration.settings_json["scheduled_sync_enabled"].as_boolean() == True,
            )
        )

        # 7. Last Sync Times
        last_success = await session.scalar(
            select(SyncRun.finished_at)
            .where(
                SyncRun.company_id == company_id,
                SyncRun.status == SyncRunStatus.SUCCESS.value,
            )
            .order_by(SyncRun.finished_at.desc())
            .limit(1)
        )
        last_failed = await session.scalar(
            select(SyncRun.finished_at)
            .where(
                SyncRun.company_id == company_id,
                SyncRun.status == SyncRunStatus.FAILED.value,
            )
            .order_by(SyncRun.finished_at.desc())
            .limit(1)
        )

        return OpsStatusResponse(
            company_id=str(company_id),
            sync_runs=sync_runs_dict,
            queued_sync_count=sync_runs_dict.get(SyncRunStatus.QUEUED.value, 0),
            running_sync_count=sync_runs_dict.get(SyncRunStatus.RUNNING.value, 0),
            stuck_queued_sync_count=stuck_queued or 0,
            stuck_running_sync_count=stuck_running or 0,
            pending_notification_events_count=pending_notifs or 0,
            failed_notification_events_count=failed_notifs or 0,
            pending_domain_events_count=pending_events or 0,
            failed_domain_events_count=failed_events or 0,
            recent_failed_sync_errors_count=recent_errors or 0,
            active_integrations_count=active_integrations or 0,
            scheduled_integrations_count=scheduled_integrations or 0,
            last_successful_sync_time=last_success,
            last_failed_sync_time=last_failed,
        )


class SyncRecoveryService:
    async def recover_stuck_sync_runs(
        self,
        session: AsyncSession,
        *,
        company_id: UUID | None = None,
        queued_timeout_minutes: int | None = None,
        running_timeout_minutes: int | None = None,
    ) -> RecoverStuckSyncsResponse:
        now = utc_now()
        q_timeout = queued_timeout_minutes or settings.sync_queued_timeout_minutes
        r_timeout = running_timeout_minutes or settings.sync_running_timeout_minutes

        q_deadline = now - timedelta(minutes=q_timeout)
        r_deadline = now - timedelta(minutes=r_timeout)

        # Recover QUEUED
        q_filters = [
            SyncRun.status == SyncRunStatus.QUEUED.value,
            SyncRun.created_at < q_deadline,
        ]
        if company_id:
            q_filters.append(SyncRun.company_id == company_id)

        q_stmt = (
            update(SyncRun)
            .where(*q_filters)
            .values(
                status=SyncRunStatus.FAILED.value,
                error_summary="Queued sync expired before worker execution",
                finished_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        q_result = await session.execute(q_stmt)
        recovered_q = q_result.rowcount

        # Recover RUNNING
        r_filters = [
            SyncRun.status == SyncRunStatus.RUNNING.value,
            SyncRun.started_at < r_deadline,
        ]
        if company_id:
            r_filters.append(SyncRun.company_id == company_id)

        r_stmt = (
            update(SyncRun)
            .where(*r_filters)
            .values(
                status=SyncRunStatus.FAILED.value,
                error_summary="Running sync exceeded timeout and was marked failed",
                finished_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        r_result = await session.execute(r_stmt)
        recovered_r = r_result.rowcount

        if recovered_q > 0 or recovered_r > 0:
            logger.info(
                f"Recovered stuck sync runs: {recovered_q} queued, {recovered_r} running. "
                f"Company: {company_id or 'global'}"
            )

        return RecoverStuckSyncsResponse(
            checked_count=recovered_q + recovered_r,  # simplified
            recovered_queued_count=recovered_q,
            recovered_running_count=recovered_r,
        )


class NotificationRecoveryService:
    async def recover_notifications(
        self,
        session: AsyncSession,
        *,
        company_id: UUID | None = None,
        pending_timeout_minutes: int | None = None,
        max_attempts: int | None = None,
    ) -> RecoverNotificationsResponse:
        now = utc_now()
        p_timeout = pending_timeout_minutes or settings.notification_pending_timeout_minutes
        m_attempts = max_attempts or settings.notification_max_attempts

        p_deadline = now - timedelta(minutes=p_timeout)

        # Mark as FAILED if too old AND max attempts reached
        filters = [
            NotificationEvent.status == NotificationEventStatus.PENDING.value,
            NotificationEvent.created_at < p_deadline,
            NotificationEvent.attempts >= m_attempts,
        ]
        if company_id:
            filters.append(NotificationEvent.company_id == company_id)

        stmt = (
            update(NotificationEvent)
            .where(*filters)
            .values(
                status=NotificationEventStatus.FAILED.value,
                last_error=f"Notification expired in pending state after {m_attempts} attempts",
                failed_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        result = await session.execute(stmt)
        failed_count = result.rowcount

        if failed_count > 0:
            logger.info(
                f"Recovered (failed) old pending notifications: {failed_count}. "
                f"Company: {company_id or 'global'}"
            )

        return RecoverNotificationsResponse(
            checked_count=failed_count,  # simplified
            failed_count=failed_count,
            retried_count=0,  # Retries are handled by the main notification task
        )


ops_service = OpsService()
sync_recovery_service = SyncRecoveryService()
notification_recovery_service = NotificationRecoveryService()
