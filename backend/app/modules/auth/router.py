from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import (
    AuthTokenResponse,
    LoginRequest,
    LogoutRequest,
    LogoutResponse,
    MeResponse,
    PlatformLoginRequest,
    RefreshTokenRequest,
    RegisterCompanyRequest,
)
from app.modules.auth.service import AuthenticatedUser, auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/register-company", response_model=AuthTokenResponse, status_code=201)
async def register_company(
    data: RegisterCompanyRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AuthTokenResponse:
    return await auth_service.register_company_owner(
        session,
        data=data,
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
    )


@router.post("/login", response_model=AuthTokenResponse)
async def login(
    data: LoginRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AuthTokenResponse:
    return await auth_service.login(
        session,
        data=data,
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
    )


@router.post("/platform-login", response_model=AuthTokenResponse)
async def platform_login(
    data: PlatformLoginRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AuthTokenResponse:
    return await auth_service.platform_login(
        session,
        data=data,
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
    )


@router.post("/refresh", response_model=AuthTokenResponse)
async def refresh(
    data: RefreshTokenRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AuthTokenResponse:
    return await auth_service.refresh(
        session,
        refresh_token=data.refresh_token,
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    data: LogoutRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LogoutResponse:
    await auth_service.logout(session, refresh_token=data.refresh_token)
    return LogoutResponse(success=True)


@router.get("/me", response_model=MeResponse)
async def me(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> MeResponse:
    return MeResponse(
        user=current_user.user,
        company=current_user.company,
        role=current_user.user.role,
        company_id=current_user.user.company_id,
    )

