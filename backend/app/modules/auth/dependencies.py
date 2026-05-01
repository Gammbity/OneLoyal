from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.db.session import get_db
from app.modules.auth.service import AuthenticatedUser
from app.modules.users.models import User, UserRole, UserStatus

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AuthenticatedUser:
    if credentials is None:
        raise UnauthorizedError("Authentication required.")

    payload = decode_token(credentials.credentials)
    if payload.get("token_type") != "access":
        raise UnauthorizedError("Invalid token type.")

    subject = payload.get("sub")
    if subject is None:
        raise UnauthorizedError("Token subject is missing.")

    try:
        user_id = UUID(str(subject))
    except ValueError as exc:
        raise UnauthorizedError("Invalid token subject.") from exc

    result = await session.execute(
        select(User).options(selectinload(User.company)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None or user.status != UserStatus.ACTIVE.value:
        raise UnauthorizedError("User account is not active.")
    if user.company_id is not None and user.company is None:
        raise UnauthorizedError("User company is not available.")

    return AuthenticatedUser(user=user, company=user.company)


async def require_authenticated_user(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    return current_user


def require_roles(*roles: UserRole | str) -> Callable:
    allowed_roles = {
        role.value if isinstance(role, UserRole) else role for role in roles
    }

    async def dependency(
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        if current_user.user.role not in allowed_roles:
            raise ForbiddenError("You do not have permission to perform this action.")
        return current_user

    return dependency


async def require_company_user(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    if current_user.user.company_id is None:
        raise ForbiddenError("Company user access is required.")
    if current_user.user.role == UserRole.PLATFORM_ADMIN.value:
        raise ForbiddenError("Platform admins cannot access company routes.")
    return current_user


async def require_platform_admin(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    if current_user.user.role != UserRole.PLATFORM_ADMIN.value:
        raise ForbiddenError("Platform admin access is required.")
    return current_user


async def require_owner_or_admin(
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
) -> AuthenticatedUser:
    if current_user.user.role not in {UserRole.OWNER.value, UserRole.ADMIN.value}:
        raise ForbiddenError("Owner or admin access is required.")
    return current_user
