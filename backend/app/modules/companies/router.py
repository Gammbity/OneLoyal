from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.session import get_db
from app.modules.audit.context import audit_context_from_request
from app.modules.audit.service import audit_log_service
from app.modules.auth.dependencies import (
    require_company_user,
    require_owner_or_admin,
    require_platform_admin,
)
from app.modules.auth.service import AuthenticatedUser
from app.modules.companies.models import Company
from app.modules.companies.schemas import (
    CompanyProvisionResponse,
    CompanyResponse,
    CompanySettingsResponse,
    CreateCompanyRequest,
    UpdateCompanySettingsRequest,
)
from app.modules.companies.service import company_service
from app.modules.users.schemas import UserResponse

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[CompanyResponse])
async def list_companies(
    current_user: Annotated[AuthenticatedUser, Depends(require_platform_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[CompanyResponse]:
    result = await session.execute(select(Company).order_by(Company.created_at.desc()))
    companies = result.scalars().all()
    return [CompanyResponse.model_validate(company) for company in companies]


@router.post("", response_model=CompanyProvisionResponse, status_code=201)
async def create_company(
    data: CreateCompanyRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_platform_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CompanyProvisionResponse:
    company, _, owner = await company_service.create_company_with_owner(
        session,
        company_name=data.company_name,
        company_slug=data.company_slug,
        owner_full_name=data.owner_full_name,
        owner_email=data.owner_email,
        owner_password=data.owner_password,
    )
    await session.commit()
    return CompanyProvisionResponse(
        company=CompanyResponse.model_validate(company),
        owner=UserResponse.model_validate(owner),
        login_path=f"/{company.slug}/login",
    )


@router.get("/me", response_model=CompanyResponse)
async def get_my_company(
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
) -> CompanyResponse:
    if current_user.company is None:
        raise NotFoundError("Company not found.")
    return CompanyResponse.model_validate(current_user.company)


@router.get("/me/settings", response_model=CompanySettingsResponse)
async def get_my_company_settings(
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CompanySettingsResponse:
    settings = await company_service.get_settings(
        session,
        current_user.user.company_id,
    )
    return CompanySettingsResponse.model_validate(settings)


@router.patch("/me/settings", response_model=CompanySettingsResponse)
async def update_my_company_settings(
    data: UpdateCompanySettingsRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
) -> CompanySettingsResponse:
    before = await company_service.get_settings(
        session,
        current_user.user.company_id,
    )
    before_json = {
        "sync_frequency_minutes": before.sync_frequency_minutes,
        "reward_claim_enabled_default": before.reward_claim_enabled_default,
        "data_retention_days": before.data_retention_days,
    }
    settings = await company_service.update_settings(
        session,
        company_id=current_user.user.company_id,
        data=data,
    )
    await audit_log_service.record(
        session,
        company_id=current_user.user.company_id,
        action="company_settings.updated",
        entity_type="company_settings",
        entity_id=settings.id,
        context=audit_context_from_request(
            request,
            actor_user_id=current_user.user.id,
            actor_type="user",
        ),
        before_json=before_json,
        after_json={
            "sync_frequency_minutes": settings.sync_frequency_minutes,
            "reward_claim_enabled_default": settings.reward_claim_enabled_default,
            "data_retention_days": settings.data_retention_days,
        },
    )
    await session.commit()
    return CompanySettingsResponse.model_validate(settings)
