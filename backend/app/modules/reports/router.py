from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import require_company_user
from app.modules.auth.service import AuthenticatedUser
from app.modules.reports.schemas import (
    CampaignOverviewReport,
    CloseToNextTierReportItem,
    GiftLiabilityReport,
    RewardClaimsReport,
    SalesManagerPerformanceItem,
    SyncHealthReport,
    TopCustomerReportItem,
)
from app.modules.reports.service import ReportViewer, reports_service

router = APIRouter(prefix="/reports", tags=["reports"])


def _viewer(current_user: AuthenticatedUser) -> ReportViewer:
    return ReportViewer(
        user_id=current_user.user.id,
        role=current_user.user.role,
    )


@router.get(
    "/campaigns/{campaign_id}/overview",
    response_model=CampaignOverviewReport,
)
async def get_campaign_overview(
    campaign_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignOverviewReport:
    return await reports_service.get_campaign_overview(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
        viewer=_viewer(current_user),
    )


@router.get(
    "/campaigns/{campaign_id}/top-customers",
    response_model=list[TopCustomerReportItem],
)
async def get_top_customers(
    campaign_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    min_amount: Annotated[int | None, Query(ge=0)] = None,
    tier_id: Annotated[UUID | None, Query()] = None,
) -> list[TopCustomerReportItem]:
    return await reports_service.get_top_customers(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
        viewer=_viewer(current_user),
        limit=limit,
        offset=offset,
        min_amount=min_amount,
        tier_id=tier_id,
    )


@router.get(
    "/campaigns/{campaign_id}/close-to-next-tier",
    response_model=list[CloseToNextTierReportItem],
)
async def get_close_to_next_tier(
    campaign_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    threshold_amount_minor: Annotated[int | None, Query(ge=0)] = None,
    threshold_percent: Annotated[Decimal | None, Query(ge=0, le=100)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CloseToNextTierReportItem]:
    return await reports_service.get_close_to_next_tier(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
        viewer=_viewer(current_user),
        limit=limit,
        offset=offset,
        threshold_amount_minor=threshold_amount_minor,
        threshold_percent=threshold_percent,
    )


@router.get(
    "/campaigns/{campaign_id}/gift-liability",
    response_model=GiftLiabilityReport,
)
async def get_gift_liability(
    campaign_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GiftLiabilityReport:
    return await reports_service.get_gift_liability(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
        viewer=_viewer(current_user),
    )


@router.get("/reward-claims", response_model=RewardClaimsReport)
async def get_reward_claims_report(
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    campaign_id: Annotated[UUID | None, Query()] = None,
    status: Annotated[str | None, Query(max_length=32)] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RewardClaimsReport:
    return await reports_service.get_reward_claims_report(
        session,
        company_id=current_user.user.company_id,
        viewer=_viewer(current_user),
        limit=limit,
        offset=offset,
        campaign_id=campaign_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/sync-health", response_model=SyncHealthReport)
async def get_sync_health(
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    integration_id: Annotated[UUID | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SyncHealthReport:
    return await reports_service.get_sync_health(
        session,
        company_id=current_user.user.company_id,
        limit=limit,
        offset=offset,
        integration_id=integration_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/sales-managers",
    response_model=list[SalesManagerPerformanceItem],
)
async def get_sales_manager_performance(
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    campaign_id: Annotated[UUID | None, Query()] = None,
    close_threshold_percent: Annotated[Decimal, Query(ge=0, le=100)] = Decimal("80"),
) -> list[SalesManagerPerformanceItem]:
    return await reports_service.get_sales_manager_performance(
        session,
        company_id=current_user.user.company_id,
        viewer=_viewer(current_user),
        campaign_id=campaign_id,
        close_threshold_percent=close_threshold_percent,
    )
