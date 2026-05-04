from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PaginationParams
from app.common.redaction import redact_sensitive_data
from app.core.errors import NotFoundError
from app.modules.audit.context import AuditContext, resolve_actor_type
from app.modules.audit.models import AuditLog


class AuditLogService:
    async def record(
        self,
        session: AsyncSession,
        *,
        company_id: UUID | None,
        action: str,
        entity_type: str,
        entity_id: UUID | None = None,
        context: AuditContext | None = None,
        before_json: dict[str, Any] | None = None,
        after_json: dict[str, Any] | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> AuditLog:
        actor_type = resolve_actor_type(context)
        audit_log = AuditLog(
            company_id=company_id,
            actor_user_id=context.actor_user_id if context else None,
            actor_customer_id=context.actor_customer_id if context else None,
            actor_type=actor_type,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address=context.ip_address if context else None,
            user_agent=context.user_agent if context else None,
            request_id=context.request_id if context else None,
            before_json=redact_sensitive_data(before_json or {}),
            after_json=redact_sensitive_data(after_json or {}),
            metadata_json=redact_sensitive_data(metadata_json or {}),
        )
        session.add(audit_log)
        await session.flush()
        return audit_log

    async def list_logs(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        pagination: PaginationParams,
        actor_user_id: UUID | None = None,
        actor_customer_id: UUID | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        created_at_from: datetime | None = None,
        created_at_to: datetime | None = None,
    ) -> tuple[list[AuditLog], int]:
        filters = [AuditLog.company_id == company_id]
        if actor_user_id is not None:
            filters.append(AuditLog.actor_user_id == actor_user_id)
        if actor_customer_id is not None:
            filters.append(AuditLog.actor_customer_id == actor_customer_id)
        if action is not None:
            filters.append(AuditLog.action == action)
        if entity_type is not None:
            filters.append(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            filters.append(AuditLog.entity_id == entity_id)
        if created_at_from is not None:
            filters.append(AuditLog.created_at >= created_at_from)
        if created_at_to is not None:
            filters.append(AuditLog.created_at <= created_at_to)

        query: Select[tuple[AuditLog]] = select(AuditLog).where(*filters)
        total_result = await session.execute(
            select(func.count()).select_from(select(AuditLog.id).where(*filters).subquery())
        )
        result = await session.execute(
            query.order_by(AuditLog.created_at.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        return list(result.scalars().all()), int(total_result.scalar_one())

    async def get_log(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        audit_log_id: UUID,
    ) -> AuditLog:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.id == audit_log_id,
                AuditLog.company_id == company_id,
            )
        )
        audit_log = result.scalar_one_or_none()
        if audit_log is None:
            raise NotFoundError("Audit log not found.")
        return audit_log


audit_log_service = AuditLogService()
