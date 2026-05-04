from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import (
    PaginatedResponse,
    PaginationParams,
    create_paginated_response,
)
from app.db.session import get_db
from app.modules.audit.schemas import AuditLogResponse
from app.modules.audit.service import audit_log_service
from app.modules.auth.dependencies import require_owner_or_admin
from app.modules.auth.service import AuthenticatedUser

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("", response_model=PaginatedResponse[AuditLogResponse])
async def list_audit_logs(
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends()],
    actor_user_id: Annotated[UUID | None, Query()] = None,
    actor_customer_id: Annotated[UUID | None, Query()] = None,
    action: Annotated[str | None, Query(max_length=120)] = None,
    entity_type: Annotated[str | None, Query(max_length=120)] = None,
    entity_id: Annotated[UUID | None, Query()] = None,
    created_at_from: Annotated[datetime | None, Query()] = None,
    created_at_to: Annotated[datetime | None, Query()] = None,
) -> PaginatedResponse[AuditLogResponse]:
    logs, total = await audit_log_service.list_logs(
        session,
        company_id=current_user.user.company_id,
        pagination=pagination,
        actor_user_id=actor_user_id,
        actor_customer_id=actor_customer_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        created_at_from=created_at_from,
        created_at_to=created_at_to,
    )
    return create_paginated_response(
        items=[AuditLogResponse.model_validate(log) for log in logs],
        params=pagination,
        total=total,
    )


@router.get("/{audit_log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    audit_log_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AuditLogResponse:
    audit_log = await audit_log_service.get_log(
        session,
        company_id=current_user.user.company_id,
        audit_log_id=audit_log_id,
    )
    return AuditLogResponse.model_validate(audit_log)
