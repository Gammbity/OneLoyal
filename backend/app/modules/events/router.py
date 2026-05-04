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
from app.modules.events.schemas import DomainEventResponse
from app.modules.events.service import domain_event_service

router = APIRouter(prefix="/domain-events", tags=["domain-events"])


@router.get("", response_model=PaginatedResponse[DomainEventResponse])
async def list_domain_events(
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends()],
    event_type: Annotated[str | None, Query(max_length=120)] = None,
    status: Annotated[str | None, Query(max_length=32)] = None,
    aggregate_type: Annotated[str | None, Query(max_length=120)] = None,
    customer_id: Annotated[UUID | None, Query()] = None,
    campaign_id: Annotated[UUID | None, Query()] = None,
    occurred_at_from: Annotated[datetime | None, Query()] = None,
    occurred_at_to: Annotated[datetime | None, Query()] = None,
) -> PaginatedResponse[DomainEventResponse]:
    events, total = await domain_event_service.list_events(
        session,
        company_id=current_user.user.company_id,
        pagination=pagination,
        event_type=event_type,
        status=status,
        aggregate_type=aggregate_type,
        customer_id=customer_id,
        campaign_id=campaign_id,
        occurred_at_from=occurred_at_from,
        occurred_at_to=occurred_at_to,
    )
    return create_paginated_response(
        items=[DomainEventResponse.model_validate(event) for event in events],
        params=pagination,
        total=total,
    )


@router.get("/{event_id}", response_model=DomainEventResponse)
async def get_domain_event(
    event_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DomainEventResponse:
    event = await domain_event_service.get_event(
        session,
        company_id=current_user.user.company_id,
        event_id=event_id,
    )
    return DomainEventResponse.model_validate(event)
