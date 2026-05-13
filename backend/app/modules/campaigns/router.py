from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import (
    PaginatedResponse,
    PaginationParams,
    create_paginated_response,
)
from app.db.session import get_db
from app.modules.audit.context import audit_context_from_request
from app.modules.audit.service import audit_log_service
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
from app.common.i18n import get_localized_value

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    data: CampaignCreateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> CampaignResponse:
    campaign = await campaign_service.create_campaign(
        session,
        company_id=current_user.user.company_id,
        data=data,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="campaign.created",
        entity_type="campaign",
        entity_id=campaign.id,
        context=audit_context_from_request(
            request,
            actor_user_id=current_user.user.id,
            actor_type="user",
        ),
        after_json={
            "title": campaign.title,
            "status": campaign.status,
            "start_date": campaign.start_date.isoformat(),
            "end_date": campaign.end_date.isoformat(),
            "currency": campaign.currency,
            "allow_claims": campaign.allow_claims,
        },
    )
    await session.commit()
    # localize before returning
    locale = getattr(request.state, "locale", "en")
    campaign.title = get_localized_value(campaign.title_i18n, locale) or campaign.title
    campaign.description = get_localized_value(campaign.description_i18n, locale) or campaign.description
    return CampaignResponse.model_validate(campaign)


@router.get("", response_model=PaginatedResponse[CampaignResponse])
async def list_campaigns(
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
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
    locale = getattr(request.state, "locale", "en")
    for c in campaigns:
        c.title = get_localized_value(c.title_i18n, locale) or c.title
        c.description = get_localized_value(c.description_i18n, locale) or c.description
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
    request: Request,
) -> CampaignResponse:
    campaign = await campaign_service.get_campaign(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
    )
    locale = getattr(request.state, "locale", "en")
    campaign.title = get_localized_value(campaign.title_i18n, locale) or campaign.title
    campaign.description = get_localized_value(campaign.description_i18n, locale) or campaign.description
    return CampaignResponse.model_validate(campaign)


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: UUID,
    data: CampaignUpdateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> CampaignResponse:
    before = await campaign_service.get_campaign(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
    )
    before_json = {
        "title": before.title,
        "description": before.description,
        "start_date": before.start_date.isoformat(),
        "end_date": before.end_date.isoformat(),
        "status": before.status,
        "currency": before.currency,
        "allow_claims": before.allow_claims,
    }
    campaign = await campaign_service.update_campaign(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
        data=data,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="campaign.updated",
        entity_type="campaign",
        entity_id=campaign.id,
        context=audit_context_from_request(
            request,
            actor_user_id=current_user.user.id,
            actor_type="user",
        ),
        before_json=before_json,
        after_json={
            "title": campaign.title,
            "description": campaign.description,
            "start_date": campaign.start_date.isoformat(),
            "end_date": campaign.end_date.isoformat(),
            "status": campaign.status,
            "currency": campaign.currency,
            "allow_claims": campaign.allow_claims,
        },
    )
    await session.commit()
    locale = getattr(request.state, "locale", "en")
    campaign.title = get_localized_value(campaign.title_i18n, locale) or campaign.title
    campaign.description = get_localized_value(campaign.description_i18n, locale) or campaign.description
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
    request: Request,
) -> CampaignResponse:
    before = await campaign_service.get_campaign(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
    )
    before_status = before.status
    campaign = await campaign_service.activate_campaign(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="campaign.activated",
        entity_type="campaign",
        entity_id=campaign.id,
        context=audit_context_from_request(
            request,
            actor_user_id=current_user.user.id,
            actor_type="user",
        ),
        before_json={"status": before_status},
        after_json={"status": campaign.status},
    )
    await session.commit()
    return CampaignResponse.model_validate(campaign)


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> CampaignResponse:
    before = await campaign_service.get_campaign(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
    )
    before_status = before.status
    campaign = await campaign_service.pause_campaign(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="campaign.paused",
        entity_type="campaign",
        entity_id=campaign.id,
        context=audit_context_from_request(
            request,
            actor_user_id=current_user.user.id,
            actor_type="user",
        ),
        before_json={"status": before_status},
        after_json={"status": campaign.status},
    )
    await session.commit()
    return CampaignResponse.model_validate(campaign)


@router.post("/{campaign_id}/complete", response_model=CampaignResponse)
async def complete_campaign(
    campaign_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> CampaignResponse:
    before = await campaign_service.get_campaign(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
    )
    before_status = before.status
    campaign = await campaign_service.complete_campaign(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="campaign.completed",
        entity_type="campaign",
        entity_id=campaign.id,
        context=audit_context_from_request(
            request,
            actor_user_id=current_user.user.id,
            actor_type="user",
        ),
        before_json={"status": before_status},
        after_json={"status": campaign.status},
    )
    await session.commit()
    return CampaignResponse.model_validate(campaign)


@router.post("/{campaign_id}/archive", response_model=CampaignResponse)
async def archive_campaign(
    campaign_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> CampaignResponse:
    before = await campaign_service.get_campaign(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
    )
    before_status = before.status
    campaign = await campaign_service.archive_campaign(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="campaign.archived",
        entity_type="campaign",
        entity_id=campaign.id,
        context=audit_context_from_request(
            request,
            actor_user_id=current_user.user.id,
            actor_type="user",
        ),
        before_json={"status": before_status},
        after_json={"status": campaign.status},
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
    request: Request,
) -> GiftTierResponse:
    tier = await gift_tier_service.create_tier(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
        data=data,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="gift_tier.created",
        entity_type="gift_tier",
        entity_id=tier.id,
        context=audit_context_from_request(
            request,
            actor_user_id=current_user.user.id,
            actor_type="user",
        ),
        after_json={
            "campaign_id": str(tier.campaign_id),
            "title": tier.title,
            "required_amount_minor": tier.required_amount_minor,
            "currency": tier.currency,
            "is_active": tier.is_active,
        },
    )
    await session.commit()
    locale = getattr(request.state, "locale", "en")
    tier.title = get_localized_value(tier.title_i18n, locale) or tier.title
    tier.description = get_localized_value(tier.description_i18n, locale) or tier.description
    return GiftTierResponse.model_validate(tier)


@router.get("/{campaign_id}/gift-tiers", response_model=list[GiftTierResponse])
async def list_gift_tiers(
    campaign_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> list[GiftTierResponse]:
    tiers = await gift_tier_service.list_tiers(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
    )
    locale = getattr(request.state, "locale", "en")
    for t in tiers:
        t.title = get_localized_value(t.title_i18n, locale) or t.title
        t.description = get_localized_value(t.description_i18n, locale) or t.description
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
    request: Request,
) -> GiftTierResponse:
    tier = await gift_tier_service.get_tier(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
        tier_id=tier_id,
    )
    locale = getattr(request.state, "locale", "en")
    tier.title = get_localized_value(tier.title_i18n, locale) or tier.title
    tier.description = get_localized_value(tier.description_i18n, locale) or tier.description
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
    request: Request,
) -> GiftTierResponse:
    before = await gift_tier_service.get_tier(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
        tier_id=tier_id,
    )
    before_json = {
        "title": before.title,
        "required_amount_minor": before.required_amount_minor,
        "stock_tracking_mode": before.stock_tracking_mode,
        "stock_quantity": before.stock_quantity,
        "is_active": before.is_active,
    }
    tier = await gift_tier_service.update_tier(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
        tier_id=tier_id,
        data=data,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="gift_tier.updated",
        entity_type="gift_tier",
        entity_id=tier.id,
        context=audit_context_from_request(
            request,
            actor_user_id=current_user.user.id,
            actor_type="user",
        ),
        before_json=before_json,
        after_json={
            "title": tier.title,
            "required_amount_minor": tier.required_amount_minor,
            "stock_tracking_mode": tier.stock_tracking_mode,
            "stock_quantity": tier.stock_quantity,
            "is_active": tier.is_active,
        },
    )
    await session.commit()
    locale = getattr(request.state, "locale", "en")
    tier.title = get_localized_value(tier.title_i18n, locale) or tier.title
    tier.description = get_localized_value(tier.description_i18n, locale) or tier.description
    return GiftTierResponse.model_validate(tier)


@router.delete("/{campaign_id}/gift-tiers/{tier_id}", status_code=204)
async def delete_gift_tier(
    campaign_id: UUID,
    tier_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> Response:
    before = await gift_tier_service.get_tier(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
        tier_id=tier_id,
    )
    before_json = {
        "title": before.title,
        "required_amount_minor": before.required_amount_minor,
        "is_active": before.is_active,
    }
    await gift_tier_service.delete_tier(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
        tier_id=tier_id,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="gift_tier.deleted",
        entity_type="gift_tier",
        entity_id=tier_id,
        context=audit_context_from_request(
            request,
            actor_user_id=current_user.user.id,
            actor_type="user",
        ),
        before_json=before_json,
        after_json={"deleted": True},
    )
    await session.commit()
    return Response(status_code=204)


@router.post("/{campaign_id}/gift-tiers/reorder", response_model=list[GiftTierResponse])
async def reorder_gift_tiers(
    campaign_id: UUID,
    data: GiftTierReorderRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> list[GiftTierResponse]:
    existing = await gift_tier_service.list_tiers(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
    )
    before_order = [str(tier.id) for tier in existing]
    tiers = await gift_tier_service.reorder_tiers(
        session,
        company_id=current_user.user.company_id,
        campaign_id=campaign_id,
        tier_ids=data.tier_ids,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="gift_tier.reordered",
        entity_type="campaign",
        entity_id=campaign_id,
        context=audit_context_from_request(
            request,
            actor_user_id=current_user.user.id,
            actor_type="user",
        ),
        before_json={"tier_ids": before_order},
        after_json={"tier_ids": [str(tier_id) for tier_id in data.tier_ids]},
    )
    await session.commit()
    locale = getattr(request.state, "locale", "en")
    for t in tiers:
        t.title = get_localized_value(t.title_i18n, locale) or t.title
        t.description = get_localized_value(t.description_i18n, locale) or t.description
    return [GiftTierResponse.model_validate(tier) for tier in tiers]
