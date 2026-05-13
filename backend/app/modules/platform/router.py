from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import require_platform_admin
from app.modules.auth.service import AuthenticatedUser
from app.modules.platform.schemas import (
    PlatformBillingResponse,
    PlatformOverviewResponse,
)
from app.modules.platform.service import platform_service

router = APIRouter(prefix="/platform", tags=["platform"])


@router.get("/overview", response_model=PlatformOverviewResponse)
async def get_platform_overview(
    current_user: Annotated[AuthenticatedUser, Depends(require_platform_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PlatformOverviewResponse:
    return await platform_service.get_overview(session)


@router.get("/billing", response_model=PlatformBillingResponse)
async def get_platform_billing(
    current_user: Annotated[AuthenticatedUser, Depends(require_platform_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PlatformBillingResponse:
    return await platform_service.get_billing(session)
