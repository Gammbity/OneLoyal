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
from app.modules.notifications.schemas import (
    NotificationEventResponse,
    NotificationEventStatusUpdateRequest,
    NotificationRuleCreateRequest,
    NotificationRuleResponse,
    NotificationRuleUpdateRequest,
    NotificationTemplateCreateRequest,
    NotificationTemplateResponse,
    NotificationTemplateUpdateRequest,
    ProcessPendingDomainEventsResponse,
    ProcessPendingNotificationsResponse,
)
from app.modules.notifications.service import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post(
    "/templates",
    response_model=NotificationTemplateResponse,
    status_code=201,
)
async def create_notification_template(
    data: NotificationTemplateCreateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationTemplateResponse:
    template = await notification_service.create_template(
        session,
        company_id=current_user.user.company_id,
        data=data,
    )
    await session.commit()
    return NotificationTemplateResponse.model_validate(template)


@router.get(
    "/templates",
    response_model=PaginatedResponse[NotificationTemplateResponse],
)
async def list_notification_templates(
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends()],
    channel: Annotated[str | None, Query(max_length=32)] = None,
    is_active: Annotated[bool | None, Query()] = None,
) -> PaginatedResponse[NotificationTemplateResponse]:
    templates, total = await notification_service.list_templates(
        session,
        company_id=current_user.user.company_id,
        pagination=pagination,
        channel=channel,
        is_active=is_active,
    )
    return create_paginated_response(
        items=[
            NotificationTemplateResponse.model_validate(template)
            for template in templates
        ],
        params=pagination,
        total=total,
    )


@router.get(
    "/templates/{template_id}",
    response_model=NotificationTemplateResponse,
)
async def get_notification_template(
    template_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationTemplateResponse:
    template = await notification_service.get_template(
        session,
        company_id=current_user.user.company_id,
        template_id=template_id,
    )
    return NotificationTemplateResponse.model_validate(template)


@router.patch(
    "/templates/{template_id}",
    response_model=NotificationTemplateResponse,
)
async def update_notification_template(
    template_id: UUID,
    data: NotificationTemplateUpdateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationTemplateResponse:
    template = await notification_service.update_template(
        session,
        company_id=current_user.user.company_id,
        template_id=template_id,
        data=data,
    )
    await session.commit()
    return NotificationTemplateResponse.model_validate(template)


@router.post("/rules", response_model=NotificationRuleResponse, status_code=201)
async def create_notification_rule(
    data: NotificationRuleCreateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationRuleResponse:
    rule = await notification_service.create_rule(
        session,
        company_id=current_user.user.company_id,
        data=data,
    )
    await session.commit()
    return NotificationRuleResponse.model_validate(rule)


@router.get("/rules", response_model=PaginatedResponse[NotificationRuleResponse])
async def list_notification_rules(
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends()],
    event_type: Annotated[str | None, Query(max_length=120)] = None,
    is_active: Annotated[bool | None, Query()] = None,
) -> PaginatedResponse[NotificationRuleResponse]:
    rules, total = await notification_service.list_rules(
        session,
        company_id=current_user.user.company_id,
        pagination=pagination,
        event_type=event_type,
        is_active=is_active,
    )
    return create_paginated_response(
        items=[NotificationRuleResponse.model_validate(rule) for rule in rules],
        params=pagination,
        total=total,
    )


@router.get("/rules/{rule_id}", response_model=NotificationRuleResponse)
async def get_notification_rule(
    rule_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationRuleResponse:
    rule = await notification_service.get_rule(
        session,
        company_id=current_user.user.company_id,
        rule_id=rule_id,
    )
    return NotificationRuleResponse.model_validate(rule)


@router.patch("/rules/{rule_id}", response_model=NotificationRuleResponse)
async def update_notification_rule(
    rule_id: UUID,
    data: NotificationRuleUpdateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationRuleResponse:
    rule = await notification_service.update_rule(
        session,
        company_id=current_user.user.company_id,
        rule_id=rule_id,
        data=data,
    )
    await session.commit()
    return NotificationRuleResponse.model_validate(rule)


@router.post(
    "/process-domain-events",
    response_model=ProcessPendingDomainEventsResponse,
)
async def process_domain_events(
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> ProcessPendingDomainEventsResponse:
    stats = await notification_service.process_pending_domain_events(
        session,
        company_id=current_user.user.company_id,
        limit=limit,
    )
    await session.commit()
    return stats


@router.post(
    "/process-pending-notifications",
    response_model=ProcessPendingNotificationsResponse,
)
async def process_pending_notifications(
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> ProcessPendingNotificationsResponse:
    stats = await notification_service.send_pending_notifications(
        session,
        company_id=current_user.user.company_id,
        limit=limit,
    )
    await session.commit()
    return stats


@router.get("/events", response_model=PaginatedResponse[NotificationEventResponse])
async def list_notification_events(
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends()],
    status: Annotated[str | None, Query(max_length=32)] = None,
    channel: Annotated[str | None, Query(max_length=32)] = None,
    domain_event_id: Annotated[UUID | None, Query()] = None,
    customer_id: Annotated[UUID | None, Query()] = None,
    user_id: Annotated[UUID | None, Query()] = None,
) -> PaginatedResponse[NotificationEventResponse]:
    events, total = await notification_service.list_notification_events(
        session,
        company_id=current_user.user.company_id,
        pagination=pagination,
        status=status,
        channel=channel,
        domain_event_id=domain_event_id,
        customer_id=customer_id,
        user_id=user_id,
    )
    return create_paginated_response(
        items=[NotificationEventResponse.model_validate(event) for event in events],
        params=pagination,
        total=total,
    )


@router.get("/events/{notification_event_id}", response_model=NotificationEventResponse)
async def get_notification_event(
    notification_event_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationEventResponse:
    event = await notification_service.get_notification_event(
        session,
        company_id=current_user.user.company_id,
        notification_event_id=notification_event_id,
    )
    return NotificationEventResponse.model_validate(event)


@router.post(
    "/events/{notification_event_id}/mark-sent",
    response_model=NotificationEventResponse,
)
async def mark_notification_event_sent(
    notification_event_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationEventResponse:
    event = await notification_service.mark_notification_event_sent(
        session,
        company_id=current_user.user.company_id,
        notification_event_id=notification_event_id,
    )
    await session.commit()
    return NotificationEventResponse.model_validate(event)


@router.post(
    "/events/{notification_event_id}/mark-failed",
    response_model=NotificationEventResponse,
)
async def mark_notification_event_failed(
    notification_event_id: UUID,
    data: NotificationEventStatusUpdateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationEventResponse:
    event = await notification_service.mark_notification_event_failed(
        session,
        company_id=current_user.user.company_id,
        notification_event_id=notification_event_id,
        error=data.error,
    )
    await session.commit()
    return NotificationEventResponse.model_validate(event)


@router.post(
    "/events/{notification_event_id}/mark-skipped",
    response_model=NotificationEventResponse,
)
async def mark_notification_event_skipped(
    notification_event_id: UUID,
    data: NotificationEventStatusUpdateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationEventResponse:
    event = await notification_service.mark_notification_event_skipped(
        session,
        company_id=current_user.user.company_id,
        notification_event_id=notification_event_id,
        skipped_reason=data.skipped_reason,
    )
    await session.commit()
    return NotificationEventResponse.model_validate(event)
