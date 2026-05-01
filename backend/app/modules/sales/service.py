from datetime import date
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination import PaginationParams
from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.modules.customers.models import Customer
from app.modules.sales.models import SaleDocumentKind, SaleRecord
from app.modules.sales.schemas import SaleRecordCreateRequest


def _normalize_currency(value: str) -> str:
    normalized = value.strip().upper()
    if len(normalized) != 3 or not normalized.isalpha():
        raise ValidationAppError(
            "Currency must be a 3-letter ISO currency code.",
            details={"field": "currency"},
        )
    return normalized


def _validate_document_sign(document_kind: str, amount_sign: int) -> None:
    if document_kind in {SaleDocumentKind.RETURN.value, SaleDocumentKind.REFUND.value}:
        if amount_sign != -1:
            raise ValidationAppError(
                "Returns and refunds must use amount_sign -1.",
                details={"field": "amount_sign"},
            )
    if document_kind == SaleDocumentKind.SALE.value and amount_sign != 1:
        raise ValidationAppError(
            "Sale documents must use amount_sign 1.",
            details={"field": "amount_sign"},
        )


class SaleRecordService:
    async def _get_customer(
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

    async def _ensure_source_key_available(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        source_key: str,
        exclude_record_id: UUID | None = None,
    ) -> None:
        filters = [
            SaleRecord.company_id == company_id,
            SaleRecord.source_key == source_key,
        ]
        if exclude_record_id is not None:
            filters.append(SaleRecord.id != exclude_record_id)
        result = await session.execute(select(SaleRecord.id).where(*filters))
        if result.scalar_one_or_none() is not None:
            raise ConflictError(
                "Sale record source_key already exists for this company.",
                details={"field": "source_key"},
            )

    async def create_sale_record(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        data: SaleRecordCreateRequest,
    ) -> SaleRecord:
        await self._get_customer(
            session,
            company_id=company_id,
            customer_id=data.customer_id,
        )
        source_key = data.source_key.strip()
        await self._ensure_source_key_available(
            session,
            company_id=company_id,
            source_key=source_key,
        )

        document_kind = data.document_kind.value
        _validate_document_sign(document_kind, data.amount_sign)

        sale_record = SaleRecord(
            company_id=company_id,
            customer_id=data.customer_id,
            source_type=data.source_type.value,
            source_key=source_key,
            provider=data.provider.value,
            document_kind=document_kind,
            erp_document_type=data.erp_document_type,
            external_document_id=data.external_document_id,
            external_document_number=data.external_document_number,
            external_updated_at=data.external_updated_at,
            document_date=data.document_date,
            effective_date=data.effective_date,
            gross_amount_minor=data.gross_amount_minor,
            net_amount_minor=data.net_amount_minor,
            vat_amount_minor=data.vat_amount_minor,
            discount_amount_minor=data.discount_amount_minor,
            paid_amount_minor=data.paid_amount_minor,
            debt_amount_minor=data.debt_amount_minor,
            amount_sign=data.amount_sign,
            currency=_normalize_currency(data.currency),
            currency_scale=data.currency_scale,
            payment_status=data.payment_status.value,
            document_status=data.document_status.value,
            is_deleted_in_source=data.document_status.value == "deleted",
            is_archived_in_source=False,
            source_customer_external_id=data.source_customer_external_id,
            raw_payload_json=data.raw_payload_json or {},
        )
        session.add(sale_record)
        await session.flush()
        return sale_record

    async def upsert_sale_record_by_source_key(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        data: SaleRecordCreateRequest,
    ) -> SaleRecord:
        result = await session.execute(
            select(SaleRecord).where(
                SaleRecord.company_id == company_id,
                SaleRecord.source_key == data.source_key.strip(),
            )
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            return await self.create_sale_record(
                session,
                company_id=company_id,
                data=data,
            )

        await self._get_customer(
            session,
            company_id=company_id,
            customer_id=data.customer_id,
        )
        document_kind = data.document_kind.value
        _validate_document_sign(document_kind, data.amount_sign)

        existing.customer_id = data.customer_id
        existing.source_type = data.source_type.value
        existing.provider = data.provider.value
        existing.document_kind = document_kind
        existing.erp_document_type = data.erp_document_type
        existing.external_document_id = data.external_document_id
        existing.external_document_number = data.external_document_number
        existing.external_updated_at = data.external_updated_at
        existing.document_date = data.document_date
        existing.effective_date = data.effective_date
        existing.gross_amount_minor = data.gross_amount_minor
        existing.net_amount_minor = data.net_amount_minor
        existing.vat_amount_minor = data.vat_amount_minor
        existing.discount_amount_minor = data.discount_amount_minor
        existing.paid_amount_minor = data.paid_amount_minor
        existing.debt_amount_minor = data.debt_amount_minor
        existing.amount_sign = data.amount_sign
        existing.currency = _normalize_currency(data.currency)
        existing.currency_scale = data.currency_scale
        existing.payment_status = data.payment_status.value
        existing.document_status = data.document_status.value
        existing.is_deleted_in_source = data.document_status.value == "deleted"
        existing.source_customer_external_id = data.source_customer_external_id
        existing.raw_payload_json = data.raw_payload_json or {}
        await session.flush()
        return existing

    async def list_sale_records(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        pagination: PaginationParams,
        customer_id: UUID | None = None,
        document_kind: str | None = None,
        document_status: str | None = None,
        payment_status: str | None = None,
        currency: str | None = None,
        effective_date_from: date | None = None,
        effective_date_to: date | None = None,
    ) -> tuple[list[SaleRecord], int]:
        filters = [
            SaleRecord.company_id == company_id,
            SaleRecord.deleted_at.is_(None),
        ]
        if customer_id is not None:
            filters.append(SaleRecord.customer_id == customer_id)
        if document_kind is not None:
            filters.append(SaleRecord.document_kind == document_kind)
        if document_status is not None:
            filters.append(SaleRecord.document_status == document_status)
        if payment_status is not None:
            filters.append(SaleRecord.payment_status == payment_status)
        if currency is not None:
            filters.append(SaleRecord.currency == _normalize_currency(currency))
        if effective_date_from is not None:
            filters.append(SaleRecord.effective_date >= effective_date_from)
        if effective_date_to is not None:
            filters.append(SaleRecord.effective_date <= effective_date_to)

        base_query: Select[tuple[SaleRecord]] = select(SaleRecord).where(*filters)
        total_result = await session.execute(
            select(func.count()).select_from(
                select(SaleRecord.id).where(*filters).subquery()
            )
        )
        result = await session.execute(
            base_query.order_by(SaleRecord.effective_date.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        return list(result.scalars().all()), int(total_result.scalar_one())

    async def get_sale_record(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        sale_record_id: UUID,
    ) -> SaleRecord:
        result = await session.execute(
            select(SaleRecord).where(
                SaleRecord.id == sale_record_id,
                SaleRecord.company_id == company_id,
                SaleRecord.deleted_at.is_(None),
            )
        )
        sale_record = result.scalar_one_or_none()
        if sale_record is None:
            raise NotFoundError("Sale record not found.")
        return sale_record


sale_record_service = SaleRecordService()

