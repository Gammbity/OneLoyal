from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import (
    PaginatedResponse,
    PaginationParams,
    create_paginated_response,
)
from app.db.session import get_db
from app.modules.audit.context import audit_context_from_request
from app.modules.audit.service import audit_log_service
from app.modules.auth.dependencies import get_current_user, require_owner_or_admin
from app.modules.auth.service import AuthenticatedUser
from app.modules.users.schemas import CreateUserRequest, UpdateUserRequest, UserResponse
from app.modules.users.service import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_my_user(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> UserResponse:
    return UserResponse.model_validate(current_user.user)


@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends()],
) -> PaginatedResponse[UserResponse]:
    users, total = await user_service.list_users(
        session,
        company_id=current_user.user.company_id,
        pagination=pagination,
    )
    return create_paginated_response(
        items=[UserResponse.model_validate(user) for user in users],
        params=pagination,
        total=total,
    )


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    data: CreateUserRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> UserResponse:
    user = await user_service.create_user(
        session,
        company_id=current_user.user.company_id,
        data=data,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="user.created",
        entity_type="user",
        entity_id=user.id,
        context=audit_context_from_request(
            request,
            actor_user_id=current_user.user.id,
            actor_type="user",
        ),
        after_json={
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "status": user.status,
        },
    )
    await session.commit()
    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    data: UpdateUserRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> UserResponse:
    before = await user_service.get_company_user(
        session,
        company_id=current_user.user.company_id,
        user_id=user_id,
    )
    before_json = {
        "full_name": before.full_name,
        "role": before.role,
        "status": before.status,
    }
    user = await user_service.update_user(
        session,
        company_id=current_user.user.company_id,
        user_id=user_id,
        data=data,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="user.updated",
        entity_type="user",
        entity_id=user.id,
        context=audit_context_from_request(
            request,
            actor_user_id=current_user.user.id,
            actor_type="user",
        ),
        before_json=before_json,
        after_json={
            "full_name": user.full_name,
            "role": user.role,
            "status": user.status,
        },
    )
    await session.commit()
    return UserResponse.model_validate(user)

