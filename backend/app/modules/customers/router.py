from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import (
    PaginatedResponse,
    PaginationParams,
    create_paginated_response,
)
from app.db.session import get_db
from app.modules.auth.dependencies import require_company_user, require_owner_or_admin
from app.modules.auth.service import AuthenticatedUser
from app.modules.customers.schemas import (
    AssignCustomerRequest,
    CustomerAssignmentResponse,
    CustomerCreateRequest,
    CustomerExternalRefCreateRequest,
    CustomerExternalRefResponse,
    CustomerResponse,
    CustomerUpdateRequest,
)
from app.modules.customers.service import customer_service

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("", response_model=CustomerResponse, status_code=201)
async def create_customer(
    data: CustomerCreateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CustomerResponse:
    customer = await customer_service.create_customer(
        session,
        company_id=current_user.user.company_id,
        data=data,
    )
    await session.commit()
    return CustomerResponse.model_validate(customer)


@router.get("", response_model=PaginatedResponse[CustomerResponse])
async def list_customers(
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends()],
    status: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query(max_length=255)] = None,
    phone: Annotated[str | None, Query(max_length=64)] = None,
    email: Annotated[str | None, Query(max_length=320)] = None,
    tax_id: Annotated[str | None, Query(max_length=120)] = None,
) -> PaginatedResponse[CustomerResponse]:
    customers, total = await customer_service.list_customers(
        session,
        company_id=current_user.user.company_id,
        pagination=pagination,
        status=status,
        search=search,
        phone=phone,
        email=email,
        tax_id=tax_id,
    )
    return create_paginated_response(
        items=[CustomerResponse.model_validate(customer) for customer in customers],
        params=pagination,
        total=total,
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_company_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CustomerResponse:
    customer = await customer_service.get_customer(
        session,
        company_id=current_user.user.company_id,
        customer_id=customer_id,
    )
    return CustomerResponse.model_validate(customer)


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: UUID,
    data: CustomerUpdateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CustomerResponse:
    customer = await customer_service.update_customer(
        session,
        company_id=current_user.user.company_id,
        customer_id=customer_id,
        data=data,
    )
    await session.commit()
    return CustomerResponse.model_validate(customer)


@router.delete("/{customer_id}", status_code=204)
async def delete_customer(
    customer_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await customer_service.archive_customer(
        session,
        company_id=current_user.user.company_id,
        customer_id=customer_id,
    )
    await session.commit()
    return Response(status_code=204)


@router.post(
    "/{customer_id}/external-refs",
    response_model=CustomerExternalRefResponse,
    status_code=201,
)
async def create_external_ref(
    customer_id: UUID,
    data: CustomerExternalRefCreateRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CustomerExternalRefResponse:
    external_ref = await customer_service.create_external_ref(
        session,
        company_id=current_user.user.company_id,
        customer_id=customer_id,
        data=data,
    )
    await session.commit()
    return CustomerExternalRefResponse.model_validate(external_ref)


@router.get(
    "/{customer_id}/external-refs",
    response_model=list[CustomerExternalRefResponse],
)
async def list_external_refs(
    customer_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[CustomerExternalRefResponse]:
    external_refs = await customer_service.list_external_refs(
        session,
        company_id=current_user.user.company_id,
        customer_id=customer_id,
    )
    return [
        CustomerExternalRefResponse.model_validate(external_ref)
        for external_ref in external_refs
    ]


@router.post(
    "/{customer_id}/assignments",
    response_model=CustomerAssignmentResponse,
    status_code=201,
)
async def assign_customer(
    customer_id: UUID,
    data: AssignCustomerRequest,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CustomerAssignmentResponse:
    assignment = await customer_service.assign_customer(
        session,
        company_id=current_user.user.company_id,
        customer_id=customer_id,
        sales_manager_user_id=data.sales_manager_user_id,
    )
    await session.commit()
    return CustomerAssignmentResponse.model_validate(assignment)


@router.delete("/{customer_id}/assignments/{sales_manager_user_id}", status_code=204)
async def unassign_customer(
    customer_id: UUID,
    sales_manager_user_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(require_owner_or_admin)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await customer_service.unassign_customer(
        session,
        company_id=current_user.user.company_id,
        customer_id=customer_id,
        sales_manager_user_id=sales_manager_user_id,
    )
    await session.commit()
    return Response(status_code=204)

