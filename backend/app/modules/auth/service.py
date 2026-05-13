import hashlib
import hmac
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.datetime import ensure_timezone_aware, utc_now
from app.core.errors import UnauthorizedError, ValidationAppError
from app.core.security import (
    create_access_token,
    generate_secure_token,
    verify_password,
)
from app.core.settings import get_settings
from app.modules.auth.models import UserSession
from app.modules.auth.schemas import (
    AuthTokenResponse,
    LoginRequest,
    PlatformLoginRequest,
    RegisterCompanyRequest,
)
from app.modules.companies.models import Company
from app.modules.companies.service import company_service
from app.modules.users.models import User, UserRole, UserStatus
from app.modules.users.schemas import UserResponse


@dataclass(frozen=True)
class AuthenticatedUser:
    user: User
    company: Company | None


def hash_refresh_token(token: str) -> str:
    settings = get_settings()
    return hmac.new(
        settings.secret_key.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


class AuthService:
    def _create_access_token_for_user(
        self,
        user: User,
        *,
        scope: str,
        company_slug: str | None = None,
    ) -> tuple[str, int]:
        settings = get_settings()
        expires_in = settings.access_token_expire_minutes * 60
        claims = {"role": user.role, "scope": scope}
        if user.company_id is not None:
            claims["company_id"] = str(user.company_id)
        if company_slug is not None:
            claims["company_slug"] = company_slug

        token = create_access_token(
            subject=str(user.id),
            expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
            extra_claims=claims,
        )
        return token, expires_in

    async def _create_refresh_session(
        self,
        session: AsyncSession,
        *,
        user: User,
        user_agent: str | None,
        ip_address: str | None,
    ) -> tuple[str, UserSession]:
        settings = get_settings()
        raw_token = generate_secure_token(48)
        user_session = UserSession(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token(raw_token),
            expires_at=utc_now() + timedelta(days=settings.refresh_token_expire_days),
            user_agent=user_agent,
            ip_address=ip_address,
        )
        session.add(user_session)
        await session.flush()
        return raw_token, user_session

    def _build_token_response(
        self,
        *,
        user: User,
        company: Company | None,
        refresh_token: str,
        scope: str,
    ) -> AuthTokenResponse:
        access_token, expires_in = self._create_access_token_for_user(
            user,
            scope=scope,
            company_slug=company.slug if company is not None else None,
        )
        return AuthTokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            user=UserResponse.model_validate(user),
            company=company,
        )

    async def register_company_owner(
        self,
        session: AsyncSession,
        *,
        data: RegisterCompanyRequest,
        user_agent: str | None,
        ip_address: str | None,
    ) -> AuthTokenResponse:
        company, _, owner = await company_service.create_company_with_owner(
            session,
            company_name=data.company_name,
            company_slug=data.company_slug,
            owner_full_name=data.owner_full_name,
            owner_email=data.owner_email,
            owner_password=data.owner_password,
        )
        refresh_token, _ = await self._create_refresh_session(
            session,
            user=owner,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        await session.commit()
        return self._build_token_response(
            user=owner,
            company=company,
            refresh_token=refresh_token,
            scope="tenant",
        )

    async def login(
        self,
        session: AsyncSession,
        *,
        data: LoginRequest,
        user_agent: str | None,
        ip_address: str | None,
    ) -> AuthTokenResponse:
        email = data.email.strip().lower()
        if data.company_slug is not None:
            result = await session.execute(
                select(User)
                .options(selectinload(User.company))
                .join(Company)
                .where(
                    User.email == email,
                    Company.slug == data.company_slug,
                )
            )
            user = result.scalar_one_or_none()
        else:
            result = await session.execute(
                select(User)
                .options(selectinload(User.company))
                .where(User.email == email)
            )
            users = list(result.scalars().all())
            if len(users) > 1:
                raise ValidationAppError(
                    "Company slug is required for this email.",
                    details={"field": "company_slug"},
                )
            user = users[0] if users else None

        if user is None or not verify_password(data.password, user.password_hash):
            raise UnauthorizedError("Invalid email or password.")
        if user.status != UserStatus.ACTIVE.value:
            raise UnauthorizedError("User account is not active.")
        if user.role == UserRole.PLATFORM_ADMIN.value:
            raise UnauthorizedError("Platform admin must use platform login.")
        if user.company_id is None:
            raise UnauthorizedError("Tenant login requires a company account.")

        user.last_login_at = utc_now()
        refresh_token, _ = await self._create_refresh_session(
            session,
            user=user,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        await session.commit()
        return self._build_token_response(
            user=user,
            company=user.company,
            refresh_token=refresh_token,
            scope="tenant",
        )

    async def platform_login(
        self,
        session: AsyncSession,
        *,
        data: PlatformLoginRequest,
        user_agent: str | None,
        ip_address: str | None,
    ) -> AuthTokenResponse:
        result = await session.execute(
            select(User)
            .options(selectinload(User.company))
            .where(
                User.email == data.email.strip().lower(),
                User.company_id.is_(None),
                User.role == UserRole.PLATFORM_ADMIN.value,
            )
        )
        user = result.scalar_one_or_none()
        if user is None or not verify_password(data.password, user.password_hash):
            raise UnauthorizedError("Invalid platform credentials.")
        if user.status != UserStatus.ACTIVE.value:
            raise UnauthorizedError("User account is not active.")

        user.last_login_at = utc_now()
        refresh_token, _ = await self._create_refresh_session(
            session,
            user=user,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        await session.commit()
        return self._build_token_response(
            user=user,
            company=None,
            refresh_token=refresh_token,
            scope="platform",
        )

    async def refresh(
        self,
        session: AsyncSession,
        *,
        refresh_token: str,
        user_agent: str | None,
        ip_address: str | None,
    ) -> AuthTokenResponse:
        token_hash = hash_refresh_token(refresh_token)
        result = await session.execute(
            select(UserSession)
            .options(selectinload(UserSession.user).selectinload(User.company))
            .where(UserSession.refresh_token_hash == token_hash)
        )
        user_session = result.scalar_one_or_none()
        if (
            user_session is None
            or user_session.revoked_at is not None
            or ensure_timezone_aware(user_session.expires_at) <= utc_now()
        ):
            raise UnauthorizedError("Invalid refresh token.")

        user = user_session.user
        if user.status != UserStatus.ACTIVE.value:
            raise UnauthorizedError("User account is not active.")

        user_session.revoked_at = utc_now()
        new_refresh_token, _ = await self._create_refresh_session(
            session,
            user=user,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        await session.commit()
        return self._build_token_response(
            user=user,
            company=user.company,
            refresh_token=new_refresh_token,
            scope=(
                "platform"
                if user.role == UserRole.PLATFORM_ADMIN.value
                else "tenant"
            ),
        )

    async def logout(self, session: AsyncSession, *, refresh_token: str) -> None:
        token_hash = hash_refresh_token(refresh_token)
        result = await session.execute(
            select(UserSession).where(UserSession.refresh_token_hash == token_hash)
        )
        user_session = result.scalar_one_or_none()
        if user_session is not None and user_session.revoked_at is None:
            user_session.revoked_at = utc_now()
            await session.commit()


auth_service = AuthService()
