from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.session import get_db
from app.modules.auth.dependencies import require_company_user, require_owner_or_admin
from app.modules.auth.service import AuthenticatedUser
from app.modules.companies.schemas import (
    CompanyResponse,
    CompanySettingsResponse,
    UpdateCompanySettingsRequest,
)
from app.modules.companies.service import company_service

router = APIRouter(prefix="/companies", tags=["companies"])


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
) -> CompanySettingsResponse:
    settings = await company_service.update_settings(
        session,
        company_id=current_user.user.company_id,
        data=data,
    )
    await session.commit()
    return CompanySettingsResponse.model_validate(settings)
