import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.core.security import hash_password
from app.core.settings import get_settings
from app.modules.billing.service import billing_service
from app.modules.companies.models import Company, CompanySettings
from app.modules.companies.schemas import UpdateCompanySettingsRequest
from app.modules.users.models import User, UserRole, UserStatus


def normalize_slug(value: str) -> str:
    normalized = value.strip().lower()
    reserved_slugs = {"platform", "admin", "api", "login", "portal"}
    if not normalized or not normalized.replace("-", "").isalnum():
        raise ValidationAppError(
            message="Company slug may contain only letters, numbers, and hyphens.",
            details={"field": "company_slug"},
        )
    if normalized in reserved_slugs:
        raise ValidationAppError(
            message="Company slug is reserved.",
            details={"field": "company_slug"},
        )
    return normalized


def slugify_company_name(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    if not normalized:
        raise ValidationAppError(
            message="Company name must contain at least one letter or number.",
            details={"field": "company_name"},
        )
    return normalized


class CompanyService:
    async def get_company(self, session: AsyncSession, company_id: UUID) -> Company:
        company = await session.get(Company, company_id)
        if company is None:
            raise NotFoundError("Company not found.")
        return company

    async def get_settings(
        self,
        session: AsyncSession,
        company_id: UUID,
    ) -> CompanySettings:
        result = await session.execute(
            select(CompanySettings).where(CompanySettings.company_id == company_id)
        )
        settings = result.scalar_one_or_none()
        if settings is None:
            raise NotFoundError("Company settings not found.")
        return settings

    async def ensure_slug_available(self, session: AsyncSession, slug: str) -> None:
        result = await session.execute(select(Company.id).where(Company.slug == slug))
        if result.scalar_one_or_none() is not None:
            raise ConflictError(
                "Company slug is already in use.",
                details={"field": "company_slug"},
            )

    async def create_company_with_owner(
        self,
        session: AsyncSession,
        *,
        company_name: str,
        company_slug: str | None = None,
        owner_full_name: str | None = None,
        owner_email: str,
        owner_password: str,
    ) -> tuple[Company, CompanySettings, User]:
        app_settings = get_settings()
        if len(owner_password) < app_settings.password_min_length:
            raise ValidationAppError(
                "Password is too short.",
                details={"min_length": app_settings.password_min_length},
            )

        slug_source = company_slug or slugify_company_name(company_name)
        slug = normalize_slug(slug_source)
        email = owner_email.strip().lower()
        await self.ensure_slug_available(session, slug)

        company = Company(name=company_name.strip(), slug=slug)
        session.add(company)
        await session.flush()

        company_settings = CompanySettings(company_id=company.id)
        session.add(company_settings)

        owner = User(
            company_id=company.id,
            email=email,
            full_name=(owner_full_name or company_name).strip(),
            password_hash=hash_password(owner_password),
            role=UserRole.OWNER.value,
            status=UserStatus.ACTIVE.value,
        )
        session.add(owner)
        await session.flush()

        await billing_service.assign_default_plan_to_company(
            session,
            company_id=company.id,
        )
        return company, company_settings, owner

    async def update_settings(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        data: UpdateCompanySettingsRequest,
    ) -> CompanySettings:
        settings = await self.get_settings(session, company_id)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field.endswith("_json") and value is None:
                value = {}
            setattr(settings, field, value)
        await session.flush()
        return settings


company_service = CompanyService()
