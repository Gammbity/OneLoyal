from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import (
    PaginatedResponse,
    PaginationParams,
    create_paginated_response,
)
from app.db.session import get_db
from app.modules.auth.dependencies import require_company_user, require_owner_or_admin
from app.modules.auth.service import AuthenticatedUser
from app.modules.campaigns.schemas import (
    CampaignCreateRequest,
    CampaignResponse,
    CampaignUpdateRequest,
    GiftTierCreateRequest,
    GiftTierReorderRequest,
    GiftTierResponse,
    GiftTierUpdateRequest,
)
from app.modules.campaigns.service import campaign_service, gift_tier_service

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    data: CampaignCreateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignResponse:
    campaign = await campaign_service.create_campaign(
        session,
        company_id=current_user.user.company_id,
        data=data,
    )
    await session.commit()
    return CampaignResponse.model_validate(campaign)


@router.get("", response_model=PaginatedResponse[CampaignResponse])
async def list_campaigns(
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends()],
    status: Annotated[str | None, Query()] = None,
    start_date_from: Annotated[date | None, Query()] = None,
    start_date_to: Annotated[date | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=255)] = None,
) -> PaginatedResponse[CampaignResponse]:
    campaigns, total = await campaign_service.list_campaigns(
        session,
        company_id=current_user.user.company_id,
        pagination=pagination,
        status=status,
        start_date_from=start_date_from,
        start_date_to=start_date_to,
        search=search,
    )
    return create_paginated_response(
        items=[CampaignResponse.model_validate(campaign) for campaign in campaigns],
        params=pagination,
        total=total,
    )


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignResponse:
    campaign = await campaign_service.get_campaign(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
    )
    return CampaignResponse.model_validate(campaign)


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: UUID,
    data: CampaignUpdateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignResponse:
    campaign = await campaign_service.update_campaign(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
        data=data,
    )
    await session.commit()
    return CampaignResponse.model_validate(campaign)


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await campaign_service.delete_campaign(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
    )
    await session.commit()
    return Response(status_code=204)


@router.post("/{campaign_id}/activate", response_model=CampaignResponse)
async def activate_campaign(
    campaign_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignResponse:
    campaign = await campaign_service.activate_campaign(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
    )
    await session.commit()
    return CampaignResponse.model_validate(campaign)


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignResponse:
    campaign = await campaign_service.pause_campaign(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
    )
    await session.commit()
    return CampaignResponse.model_validate(campaign)


@router.post("/{campaign_id}/complete", response_model=CampaignResponse)
async def complete_campaign(
    campaign_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignResponse:
    campaign = await campaign_service.complete_campaign(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
    )
    await session.commit()
    return CampaignResponse.model_validate(campaign)


@router.post("/{campaign_id}/archive", response_model=CampaignResponse)
async def archive_campaign(
    campaign_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignResponse:
    campaign = await campaign_service.archive_campaign(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
    )
    await session.commit()
    return CampaignResponse.model_validate(campaign)


@router.post(
    "/{campaign_id}/gift-tiers",
    response_model=GiftTierResponse,
    status_code=201,
)
async def create_gift_tier(
    campaign_id: UUID,
    data: GiftTierCreateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GiftTierResponse:
    tier = await gift_tier_service.create_tier(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
        data=data,
    )
    await session.commit()
    return GiftTierResponse.model_validate(tier)


@router.get("/{campaign_id}/gift-tiers", response_model=list[GiftTierResponse])
async def list_gift_tiers(
    campaign_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[GiftTierResponse]:
    tiers = await gift_tier_service.list_tiers(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
    )
    return [GiftTierResponse.model_validate(tier) for tier in tiers]


@router.get(
    "/{campaign_id}/gift-tiers/{tier_id}",
    response_model=GiftTierResponse,
)
async def get_gift_tier(
    campaign_id: UUID,
    tier_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GiftTierResponse:
    tier = await gift_tier_service.get_tier(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
        tier_id=tier_id,
    )
    return GiftTierResponse.model_validate(tier)


@router.patch(
    "/{campaign_id}/gift-tiers/{tier_id}",
    response_model=GiftTierResponse,
)
async def update_gift_tier(
    campaign_id: UUID,
    tier_id: UUID,
    data: GiftTierUpdateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GiftTierResponse:
    tier = await gift_tier_service.update_tier(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
        tier_id=tier_id,
        data=data,
    )
    await session.commit()
    return GiftTierResponse.model_validate(tier)


@router.delete("/{campaign_id}/gift-tiers/{tier_id}", status_code=204)
async def delete_gift_tier(
    campaign_id: UUID,
    tier_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await gift_tier_service.delete_tier(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
        tier_id=tier_id,
    )
    await session.commit()
    return Response(status_code=204)


@router.post("/{campaign_id}/gift-tiers/reorder", response_model=list[GiftTierResponse])
async def reorder_gift_tiers(
    campaign_id: UUID,
    data: GiftTierReorderRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[GiftTierResponse]:
    tiers = await gift_tier_service.reorder_tiers(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
        tier_ids=data.tier_ids,
    )
    await session.commit()
    return [GiftTierResponse.model_validate(tier) for tier in tiers]
