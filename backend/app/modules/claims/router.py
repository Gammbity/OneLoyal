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
from app.modules.audit.service import audit_log_service
from app.modules.auth.dependencies import require_company_user, require_owner_or_admin
from app.modules.auth.service import AuthenticatedUser
from app.modules.claims.schemas import (
    RewardClaimActionRequest,
    RewardClaimCreateRequest,
    RewardClaimResponse,
)
from app.modules.claims.service import reward_claim_service

router = APIRouter(prefix="/reward-claims", tags=["reward-claims"])


@router.get("", response_model=PaginatedResponse[RewardClaimResponse])
async def list_reward_claims(
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends()],
    campaign_id: Annotated[UUID | None, Query()] = None,
    customer_id: Annotated[UUID | None, Query()] = None,
    gift_tier_id: Annotated[UUID | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
) -> PaginatedResponse[RewardClaimResponse]:
    claims, total = await reward_claim_service.list_claims(
        session,
        company_id=current_user.user.company_id,
        pagination=pagination,
        campaign_id=campaign_id,
        customer_id=customer_id,
        gift_tier_id=gift_tier_id,
        status=status,
    )
    return create_paginated_response(
        items=[RewardClaimResponse.model_validate(claim) for claim in claims],
        params=pagination,
        total=total,
    )


@router.get("/{claim_id}", response_model=RewardClaimResponse)
async def get_reward_claim(
    claim_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RewardClaimResponse:
    claim = await reward_claim_service.get_claim(
        session,
        company_id=current_user.user.company_id,
        claim_id=claim_id,
    )
    return RewardClaimResponse.model_validate(claim)


@router.post("", response_model=RewardClaimResponse, status_code=201)
async def create_reward_claim(
    data: RewardClaimCreateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> RewardClaimResponse:
    event_context = audit_context_from_request(
        request,
        actor_user_id=current_user.user.id,
        actor_type="user",
    )
    claim = await reward_claim_service.create_claim(
        session,
        company_id=current_user.user.company_id,
        data=data,
        event_context=event_context,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="reward_claim.created",
        entity_type="reward_claim",
        entity_id=claim.id,
        context=event_context,
        after_json={
            "status": claim.status,
            "campaign_id": str(claim.campaign_id),
            "customer_id": str(claim.customer_id),
            "gift_tier_id": str(claim.gift_tier_id),
        },
    )
    await session.commit()
    return RewardClaimResponse.model_validate(claim)


@router.post("/{claim_id}/approve", response_model=RewardClaimResponse)
async def approve_reward_claim(
    claim_id: UUID,
    data: RewardClaimActionRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> RewardClaimResponse:
    event_context = audit_context_from_request(
        request,
        actor_user_id=current_user.user.id,
        actor_type="user",
    )
    claim = await reward_claim_service.approve_claim(
        session,
        company_id=current_user.user.company_id,
        claim_id=claim_id,
        decided_by_user_id=current_user.user.id,
        admin_comment=data.admin_comment,
        event_context=event_context,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="reward_claim.approved",
        entity_type="reward_claim",
        entity_id=claim.id,
        context=event_context,
        after_json={
            "status": claim.status,
            "campaign_id": str(claim.campaign_id),
            "customer_id": str(claim.customer_id),
            "gift_tier_id": str(claim.gift_tier_id),
        },
    )
    await session.commit()
    return RewardClaimResponse.model_validate(claim)


@router.post("/{claim_id}/reject", response_model=RewardClaimResponse)
async def reject_reward_claim(
    claim_id: UUID,
    data: RewardClaimActionRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> RewardClaimResponse:
    event_context = audit_context_from_request(
        request,
        actor_user_id=current_user.user.id,
        actor_type="user",
    )
    claim = await reward_claim_service.reject_claim(
        session,
        company_id=current_user.user.company_id,
        claim_id=claim_id,
        decided_by_user_id=current_user.user.id,
        admin_comment=data.admin_comment,
        event_context=event_context,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="reward_claim.rejected",
        entity_type="reward_claim",
        entity_id=claim.id,
        context=event_context,
        after_json={
            "status": claim.status,
            "campaign_id": str(claim.campaign_id),
            "customer_id": str(claim.customer_id),
            "gift_tier_id": str(claim.gift_tier_id),
        },
    )
    await session.commit()
    return RewardClaimResponse.model_validate(claim)


@router.post("/{claim_id}/fulfill", response_model=RewardClaimResponse)
async def fulfill_reward_claim(
    claim_id: UUID,
    data: RewardClaimActionRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> RewardClaimResponse:
    event_context = audit_context_from_request(
        request,
        actor_user_id=current_user.user.id,
        actor_type="user",
    )
    claim = await reward_claim_service.fulfill_claim(
        session,
        company_id=current_user.user.company_id,
        claim_id=claim_id,
        fulfilled_by_user_id=current_user.user.id,
        admin_comment=data.admin_comment,
        event_context=event_context,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="reward_claim.fulfilled",
        entity_type="reward_claim",
        entity_id=claim.id,
        context=event_context,
        after_json={
            "status": claim.status,
            "campaign_id": str(claim.campaign_id),
            "customer_id": str(claim.customer_id),
            "gift_tier_id": str(claim.gift_tier_id),
        },
    )
    await session.commit()
    return RewardClaimResponse.model_validate(claim)


@router.post("/{claim_id}/cancel", response_model=RewardClaimResponse)
async def cancel_reward_claim(
    claim_id: UUID,
    data: RewardClaimActionRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> RewardClaimResponse:
    event_context = audit_context_from_request(
        request,
        actor_user_id=current_user.user.id,
        actor_type="user",
    )
    claim = await reward_claim_service.cancel_claim(
        session,
        company_id=current_user.user.company_id,
        claim_id=claim_id,
        cancelled_by_user_id=current_user.user.id,
        admin_comment=data.admin_comment,
        event_context=event_context,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="reward_claim.cancelled",
        entity_type="reward_claim",
        entity_id=claim.id,
        context=event_context,
        after_json={
            "status": claim.status,
            "campaign_id": str(claim.campaign_id),
            "customer_id": str(claim.customer_id),
            "gift_tier_id": str(claim.gift_tier_id),
        },
    )
    await session.commit()
    return RewardClaimResponse.model_validate(claim)
