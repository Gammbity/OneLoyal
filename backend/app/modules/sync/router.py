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
from app.modules.auth.dependencies import require_owner_or_admin
from app.modules.auth.service import AuthenticatedUser
from app.modules.sync.schemas import SyncErrorResponse, SyncRunResponse
from app.modules.sync.service import sync_service

router = APIRouter(prefix="/sync-runs", tags=["sync-runs"])


@router.get("", response_model=PaginatedResponse[SyncRunResponse])
async def list_sync_runs(
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends()],
    integration_id: Annotated[UUID | None, Query()] = None,
    status: Annotated[str | None, Query(max_length=32)] = None,
    sync_type: Annotated[str | None, Query(max_length=32)] = None,
    started_at_from: Annotated[datetime | None, Query()] = None,
    started_at_to: Annotated[datetime | None, Query()] = None,
) -> PaginatedResponse[SyncRunResponse]:
    sync_runs, total = await sync_service.list_sync_runs(
        session,
        company_id=current_user.user.company_id,
        pagination=pagination,
        integration_id=integration_id,
        status=status,
        sync_type=sync_type,
        started_at_from=started_at_from,
        started_at_to=started_at_to,
    )
    return create_paginated_response(
        items=[SyncRunResponse.model_validate(sync_run) for sync_run in sync_runs],
        params=pagination,
        total=total,
    )


@router.get("/{sync_run_id}", response_model=SyncRunResponse)
async def get_sync_run(
    sync_run_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SyncRunResponse:
    sync_run = await sync_service.get_sync_run(
        session,
        company_id=current_user.user.company_id,
        sync_run_id=sync_run_id,
    )
    return SyncRunResponse.model_validate(sync_run)


@router.get(
    "/{sync_run_id}/errors",
    response_model=PaginatedResponse[SyncErrorResponse],
)
async def list_sync_errors(
    sync_run_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends()],
) -> PaginatedResponse[SyncErrorResponse]:
    errors, total = await sync_service.list_sync_errors(
        session,
        company_id=current_user.user.company_id,
        sync_run_id=sync_run_id,
        pagination=pagination,
    )
    return create_paginated_response(
        items=[SyncErrorResponse.model_validate(error) for error in errors],
        params=pagination,
        total=total,
    )
