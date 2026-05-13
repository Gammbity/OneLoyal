from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.pagination import PaginationParams
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationAppError,
)
from app.core.security import hash_password
from app.core.settings import get_settings
from app.modules.events.service import domain_event_service
from app.modules.users.models import User, UserRole, UserStatus
from app.modules.users.schemas import CreateUserRequest, UpdateUserRequest


def normalize_email(value: str) -> str:
    return value.strip().lower()


class UserService:
    async def get_user_by_email(
        self,
        session: AsyncSession,
        email: str,
        *,
        company_id: UUID | None = None,
    ) -> User | None:
        query = select(User).options(selectinload(User.company)).where(
            User.email == normalize_email(email)
        )
        if company_id is not None:
            query = query.where(User.company_id == company_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def get_user(self, session: AsyncSession, user_id: UUID) -> User:
        user = await session.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found.")
        return user

    async def get_company_user(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        user_id: UUID,
    ) -> User:
        result = await session.execute(
            select(User).where(User.company_id == company_id, User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise NotFoundError("User not found.")
        return user

    async def list_users(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        pagination: PaginationParams,
    ) -> tuple[list[User], int]:
        base_query: Select[tuple[User]] = select(User).where(
            User.company_id == company_id
        )
        total_result = await session.execute(
            select(func.count()).select_from(
                select(User.id).where(User.company_id == company_id).subquery()
            )
        )
        result = await session.execute(
            base_query.order_by(User.created_at.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        return list(result.scalars().all()), int(total_result.scalar_one())

    async def create_user(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        data: CreateUserRequest,
    ) -> User:
        if data.role not in {UserRole.ADMIN, UserRole.SALES_MANAGER}:
            raise ForbiddenError(
                "Only admin and sales manager users can be created here."
            )

        app_settings = get_settings()
        if len(data.password) < app_settings.password_min_length:
            raise ValidationAppError(
                "Password is too short.",
                details={"min_length": app_settings.password_min_length},
            )

        email = normalize_email(data.email)
        existing = await self.get_user_by_email(session, email, company_id=company_id)
        if existing is not None:
            raise ConflictError("Email is already in use.", details={"field": "email"})

        user = User(
            company_id=company_id,
            email=email,
            full_name=data.full_name.strip(),
            password_hash=hash_password(data.password),
            role=data.role.value,
            status=UserStatus.ACTIVE.value,
        )
        session.add(user)
        await session.flush()

        await domain_event_service.emit(
            session,
            company_id=company_id,
            event_type="user.created",
            aggregate_type="user",
            aggregate_id=user.id,
            actor_user_id=user.id,  # User created themselves (or system)
            payload_json={
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "secret_token": "SHOULD_BE_REDACTED",  # Test for redaction
            },
        )
        return user

    async def update_user(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        user_id: UUID,
        data: UpdateUserRequest,
    ) -> User:
        user = await self.get_company_user(
            session,
            company_id=company_id,
            user_id=user_id,
        )
        update_data = data.model_dump(exclude_unset=True)

        if "role" in update_data and update_data["role"] is not None:
            role = update_data["role"]
            if role not in {UserRole.ADMIN, UserRole.SALES_MANAGER}:
                raise ForbiddenError(
                    "Only admin and sales manager roles are allowed here."
                )
            user.role = role.value

        if "status" in update_data and update_data["status"] is not None:
            status = update_data["status"]
            if status == UserStatus.INVITED:
                raise ValidationAppError("Invited status is reserved for invitations.")
            user.status = status.value

        if "full_name" in update_data and update_data["full_name"] is not None:
            user.full_name = update_data["full_name"].strip()

        await session.flush()
        return user

    async def disable_user(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        user_id: UUID,
    ) -> User:
        user = await self.get_company_user(
            session,
            company_id=company_id,
            user_id=user_id,
        )
        user.status = UserStatus.DISABLED.value
        await session.flush()
        return user


user_service = UserService()
