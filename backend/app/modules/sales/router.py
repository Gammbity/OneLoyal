from datetime import date
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
from app.modules.auth.dependencies import require_company_user, require_owner_or_admin
from app.modules.auth.service import AuthenticatedUser
from app.modules.sales.schemas import SaleRecordCreateRequest, SaleRecordResponse
from app.modules.sales.service import sale_record_service

router = APIRouter(prefix="/sale-records", tags=["sale-records"])


@router.post("", response_model=SaleRecordResponse, status_code=201)
async def create_sale_record(
    data: SaleRecordCreateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SaleRecordResponse:
    sale_record = await sale_record_service.create_sale_record(
        session,
        company_id=current_user.user.company_id,
        data=data,
    )
    await session.commit()
    return SaleRecordResponse.model_validate(sale_record)


@router.get("", response_model=PaginatedResponse[SaleRecordResponse])
async def list_sale_records(
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends()],
    customer_id: Annotated[UUID | None, Query()] = None,
    document_kind: Annotated[str | None, Query(max_length=32)] = None,
    document_status: Annotated[str | None, Query(max_length=32)] = None,
    payment_status: Annotated[str | None, Query(max_length=32)] = None,
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    effective_date_from: Annotated[date | None, Query()] = None,
    effective_date_to: Annotated[date | None, Query()] = None,
) -> PaginatedResponse[SaleRecordResponse]:
    sale_records, total = await sale_record_service.list_sale_records(
        session,
        company_id=current_user.user.company_id,
        pagination=pagination,
        customer_id=customer_id,
        document_kind=document_kind,
        document_status=document_status,
        payment_status=payment_status,
        currency=currency,
        effective_date_from=effective_date_from,
        effective_date_to=effective_date_to,
    )
    return create_paginated_response(
        items=[
            SaleRecordResponse.model_validate(sale_record)
            for sale_record in sale_records
        ],
        params=pagination,
        total=total,
    )


@router.get("/{sale_record_id}", response_model=SaleRecordResponse)
async def get_sale_record(
    sale_record_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SaleRecordResponse:
    sale_record = await sale_record_service.get_sale_record(
        session,
        company_id=current_user.user.company_id,
        sale_record_id=sale_record_id,
    )
    return SaleRecordResponse.model_validate(sale_record)

