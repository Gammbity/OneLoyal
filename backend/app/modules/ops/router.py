from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import AuthenticatedUser, require_owner_or_admin
from app.modules.ops.schemas import (
    OpsStatusResponse,
    RecoverNotificationsResponse,
    RecoverStuckSyncsResponse,
)
from app.modules.ops.service import (
    notification_recovery_service,
    ops_service,
    sync_recovery_service,
)

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/status", response_model=OpsStatusResponse)
async def get_ops_status(
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> OpsStatusResponse:
    return await ops_service.get_status(
        session,
        company_id=current_user.user.company_id,
    )


@router.post("/recover-stuck-syncs", response_model=RecoverStuckSyncsResponse)
async def recover_stuck_syncs(
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    queued_timeout_minutes: Annotated[int | None, Query(ge=1, le=1440)] = None,
    running_timeout_minutes: Annotated[int | None, Query(ge=1, le=1440)] = None,
) -> RecoverStuckSyncsResponse:
    result = await sync_recovery_service.recover_stuck_sync_runs(
        session,
        company_id=current_user.user.company_id,
        queued_timeout_minutes=queued_timeout_minutes,
        running_timeout_minutes=running_timeout_minutes,
    )
    await session.commit()
    return result


@router.post("/recover-notifications", response_model=RecoverNotificationsResponse)
async def recover_notifications(
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    pending_timeout_minutes: Annotated[int | None, Query(ge=1, le=1440)] = None,
    max_attempts: Annotated[int | None, Query(ge=1, le=10)] = None,
) -> RecoverNotificationsResponse:
    result = await notification_recovery_service.recover_notifications(
        session,
        company_id=current_user.user.company_id,
        pending_timeout_minutes=pending_timeout_minutes,
        max_attempts=max_attempts,
    )
    await session.commit()
    return result
