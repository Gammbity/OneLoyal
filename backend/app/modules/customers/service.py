from uuid import UUID

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PaginationParams
from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.modules.customers.models import (
    Customer,
    CustomerAssignment,
    CustomerExternalRef,
    CustomerStatus,
)
from app.modules.customers.schemas import (
    CustomerCreateRequest,
    CustomerExternalRefCreateRequest,
    CustomerUpdateRequest,
)
from app.modules.events.service import domain_event_service
from app.modules.users.models import User, UserRole


class CustomerService:
    async def create_customer(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        data: CustomerCreateRequest,
    ) -> Customer:
        customer = Customer(
            company_id=company_id,
            name=data.name.strip(),
            phone=data.phone,
            email=str(data.email).lower() if data.email else None,
            tax_id=data.tax_id,
            status=CustomerStatus.ACTIVE.value,
            metadata_json=data.metadata_json or {},
        )
        session.add(customer)
        await session.flush()

        await domain_event_service.emit(
            session,
            company_id=company_id,
            event_type="customer.created",
            aggregate_type="customer",
            aggregate_id=customer.id,
            customer_id=customer.id,
            payload_json={
                "id": str(customer.id),
                "name": customer.name,
                "email": customer.email,
            },
        )
        return customer

    async def list_customers(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        pagination: PaginationParams,
        status: str | None = None,
        search: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        tax_id: str | None = None,
    ) -> tuple[list[Customer], int]:
        filters = [Customer.company_id == company_id, Customer.deleted_at.is_(None)]
        if status is not None:
            filters.append(Customer.status == status)
        if phone is not None:
            filters.append(Customer.phone == phone)
        if email is not None:
            filters.append(Customer.email == email.lower())
        if tax_id is not None:
            filters.append(Customer.tax_id == tax_id)
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                Customer.name.ilike(pattern)
                | Customer.email.ilike(pattern)
                | Customer.phone.ilike(pattern)
                | Customer.tax_id.ilike(pattern)
            )

        base_query: Select[tuple[Customer]] = select(Customer).where(*filters)
        total_result = await session.execute(
            select(func.count()).select_from(
                select(Customer.id).where(*filters).subquery()
            )
        )
        result = await session.execute(
            base_query.order_by(Customer.created_at.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        return list(result.scalars().all()), int(total_result.scalar_one())

    async def get_customer(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        customer_id: UUID,
    ) -> Customer:
        result = await session.execute(
            select(Customer).where(
                Customer.id == customer_id,
                Customer.company_id == company_id,
                Customer.deleted_at.is_(None),
            )
        )
        customer = result.scalar_one_or_none()
        if customer is None:
            raise NotFoundError("Customer not found.")
        return customer

    async def update_customer(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        customer_id: UUID,
        data: CustomerUpdateRequest,
    ) -> Customer:
        customer = await self.get_customer(
            session,
            company_id=company_id,
            customer_id=customer_id,
        )
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "name" and value is not None:
                value = value.strip()
            if field == "email" and value is not None:
                value = str(value).lower()
            if field == "status" and value is not None:
                value = value.value
            if field == "metadata_json" and value is None:
                value = {}
            setattr(customer, field, value)

        await session.flush()
        return customer

    async def archive_customer(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        customer_id: UUID,
    ) -> Customer:
        customer = await self.get_customer(
            session,
            company_id=company_id,
            customer_id=customer_id,
        )
        customer.status = CustomerStatus.ARCHIVED.value
        customer.mark_deleted()
        await session.flush()
        return customer

    async def create_external_ref(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        customer_id: UUID,
        data: CustomerExternalRefCreateRequest,
    ) -> CustomerExternalRef:
        if data.customer_id != customer_id:
            raise ValidationAppError(
                "customer_id must match the route customer_id.",
                details={"field": "customer_id"},
            )
        await self.get_customer(session, company_id=company_id, customer_id=customer_id)

        result = await session.execute(
            select(CustomerExternalRef.id).where(
                CustomerExternalRef.company_id == company_id,
                CustomerExternalRef.provider == data.provider.value,
                CustomerExternalRef.external_id == data.external_id,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise ConflictError(
                "External customer reference already exists.",
                details={"field": "external_id"},
            )

        external_ref = CustomerExternalRef(
            company_id=company_id,
            customer_id=customer_id,
            provider=data.provider.value,
            external_id=data.external_id,
            external_name=data.external_name,
            external_phone=data.external_phone,
            external_email=str(data.external_email).lower()
            if data.external_email
            else None,
            raw_payload_json=data.raw_payload_json or {},
        )
        session.add(external_ref)
        await session.flush()
        return external_ref

    async def list_external_refs(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        customer_id: UUID,
    ) -> list[CustomerExternalRef]:
        await self.get_customer(session, company_id=company_id, customer_id=customer_id)
        result = await session.execute(
            select(CustomerExternalRef)
            .where(
                CustomerExternalRef.company_id == company_id,
                CustomerExternalRef.customer_id == customer_id,
            )
            .order_by(CustomerExternalRef.created_at.desc())
        )
        return list(result.scalars().all())

    async def assign_customer(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        customer_id: UUID,
        sales_manager_user_id: UUID,
    ) -> CustomerAssignment:
        await self.get_customer(session, company_id=company_id, customer_id=customer_id)
        user = await session.get(User, sales_manager_user_id)
        if user is None or user.company_id != company_id:
            raise NotFoundError("Sales manager user not found.")
        if user.role != UserRole.SALES_MANAGER.value:
            raise ValidationAppError(
                "Assigned user must have sales_manager role.",
                details={"field": "sales_manager_user_id"},
            )

        result = await session.execute(
            select(CustomerAssignment.id).where(
                CustomerAssignment.company_id == company_id,
                CustomerAssignment.customer_id == customer_id,
                CustomerAssignment.sales_manager_user_id == sales_manager_user_id,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise ConflictError("Customer is already assigned to this sales manager.")

        assignment = CustomerAssignment(
            company_id=company_id,
            customer_id=customer_id,
            sales_manager_user_id=sales_manager_user_id,
        )
        session.add(assignment)
        await session.flush()
        return assignment

    async def unassign_customer(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        customer_id: UUID,
        sales_manager_user_id: UUID,
    ) -> None:
        await self.get_customer(session, company_id=company_id, customer_id=customer_id)
        result = await session.execute(
            delete(CustomerAssignment).where(
                CustomerAssignment.company_id == company_id,
                CustomerAssignment.customer_id == customer_id,
                CustomerAssignment.sales_manager_user_id == sales_manager_user_id,
            )
        )
        if result.rowcount == 0:
            raise NotFoundError("Customer assignment not found.")


customer_service = CustomerService()

