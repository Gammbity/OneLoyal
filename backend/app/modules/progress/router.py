from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import (
    PaginatedResponse,
    PaginationParams,
    create_paginated_response,
)
from app.db.session import get_db
from app.modules.audit.context import audit_context_from_request
from app.modules.auth.dependencies import require_company_user, require_owner_or_admin
from app.modules.auth.service import AuthenticatedUser
from app.modules.progress.schemas import (
    CustomerCampaignProgressResponse,
    RecalculateCampaignResponse,
)
from app.modules.progress.service import progress_service

router = APIRouter(prefix="/progress", tags=["progress"])


@router.post(
    "/campaigns/{campaign_id}/recalculate",
    response_model=RecalculateCampaignResponse,
)
async def recalculate_campaign_progress(
    campaign_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RecalculateCampaignResponse:
    event_context = audit_context_from_request(
        request,
        actor_user_id=current_user.user.id,
        actor_type="user",
    )
    stats = await progress_service.recalculate_campaign_progress(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
        event_context=event_context,
    )
    await session.commit()
    return RecalculateCampaignResponse(
        campaign_id=stats.campaign_id,
        recalculated_count=stats.recalculated_count,
        skipped_count=stats.skipped_count,
        failed_count=stats.failed_count,
        affected_customer_count=stats.affected_customer_count,
    )


@router.post(
    "/campaigns/{campaign_id}/customers/{customer_id}/recalculate",
    response_model=CustomerCampaignProgressResponse,
)
async def recalculate_customer_progress(
    campaign_id: UUID,
    customer_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CustomerCampaignProgressResponse:
    event_context = audit_context_from_request(
        request,
        actor_user_id=current_user.user.id,
        actor_type="user",
    )
    progress = await progress_service.calculate_customer_progress(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
        customer_id=customer_id,
        event_context=event_context,
    )
    await session.commit()
    return CustomerCampaignProgressResponse.model_validate(progress)


@router.get(
    "/campaigns/{campaign_id}",
    response_model=PaginatedResponse[CustomerCampaignProgressResponse],
)
async def list_campaign_progress(
    campaign_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends()],
    customer_id: Annotated[UUID | None, Query()] = None,
    current_tier_id: Annotated[UUID | None, Query()] = None,
    next_tier_id: Annotated[UUID | None, Query()] = None,
    min_total_amount_minor: Annotated[int | None, Query(ge=0)] = None,
    max_total_amount_minor: Annotated[int | None, Query(ge=0)] = None,
    search: Annotated[str | None, Query(max_length=255)] = None,
) -> PaginatedResponse[CustomerCampaignProgressResponse]:
    progress_items, total = await progress_service.list_campaign_progress(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
        pagination=pagination,
        customer_id=customer_id,
        current_tier_id=current_tier_id,
        next_tier_id=next_tier_id,
        min_total_amount_minor=min_total_amount_minor,
        max_total_amount_minor=max_total_amount_minor,
        search=search,
    )
    return create_paginated_response(
        items=[
            CustomerCampaignProgressResponse.model_validate(progress)
            for progress in progress_items
        ],
        params=pagination,
        total=total,
    )


@router.get(
    "/campaigns/{campaign_id}/customers/{customer_id}",
    response_model=CustomerCampaignProgressResponse,
)
async def get_customer_progress(
    campaign_id: UUID,
    customer_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CustomerCampaignProgressResponse:
    progress = await progress_service.get_customer_progress(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
        customer_id=customer_id,
    )
    return CustomerCampaignProgressResponse.model_validate(progress)

