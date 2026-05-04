import csv
import hashlib
import io
import json
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.datetime import utc_now
from app.common.pagination import PaginationParams
from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.core.settings import get_settings
from app.modules.audit.context import AuditContext
from app.modules.campaigns.models import Campaign, CampaignStatus
from app.modules.customers.models import (
    Customer,
    CustomerExternalRef,
    CustomerStatus,
)
from app.modules.events.service import domain_event_service
from app.modules.imports.models import (
    ImportBatch,
    ImportBatchStatus,
    ImportRow,
    ImportRowStatus,
)
from app.modules.progress.service import progress_service
from app.modules.sales.models import (
    PaymentStatus,
    SaleDocumentKind,
    SaleDocumentStatus,
    SaleRecord,
)
from app.modules.sales.schemas import normalize_currency

REQUIRED_COLUMNS = {
    "customer_external_id",
    "customer_name",
    "sale_date",
    "amount",
    "currency",
}


def _stable_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _empty_to_none(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _parse_date(value: Any, field: str, errors: list[str]) -> date | None:
    text = _empty_to_none(value)
    if text is None:
        errors.append(f"{field} is required.")
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        errors.append(f"{field} must use YYYY-MM-DD format.")
        return None


def _parse_int(value: Any, field: str, errors: list[str]) -> int | None:
    text = _empty_to_none(value)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        errors.append(f"{field} must be an integer.")
        return None


def _looks_like_thousands_with_commas(value: str) -> bool:
    parts = value.split(",")
    return (
        len(parts) > 1
        and 1 <= len(parts[0]) <= 3
        and all(len(part) == 3 and part.isdigit() for part in parts[1:])
    )


def _parse_amount_minor(
    value: Any,
    *,
    field: str,
    currency_scale: int,
    errors: list[str],
) -> int | None:
    text = _empty_to_none(value)
    if text is None:
        errors.append(f"{field} is required.")
        return None

    normalized = text.replace(" ", "").replace("_", "")
    if "," in normalized and "." in normalized:
        normalized = normalized.replace(",", "")
    elif "," in normalized:
        if _looks_like_thousands_with_commas(normalized):
            normalized = normalized.replace(",", "")
        else:
            normalized = normalized.replace(",", ".")

    try:
        decimal_value = Decimal(normalized)
    except InvalidOperation:
        errors.append(f"{field} must be a valid amount.")
        return None

    if decimal_value < 0:
        errors.append(f"{field} must be non-negative.")
        return None

    multiplier = Decimal(10) ** currency_scale
    minor_value = decimal_value * multiplier
    if minor_value != minor_value.to_integral_value():
        errors.append(f"{field} has too many fractional digits.")
        return None
    return int(minor_value)


def _normalize_metadata(value: Any, errors: list[str]) -> dict[str, Any]:
    text = _empty_to_none(value)
    if text is None:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        errors.append("metadata must be valid JSON.")
        return {}
    if not isinstance(parsed, dict):
        errors.append("metadata must be a JSON object.")
        return {}
    return parsed


def _detect_delimiter(text: str) -> str:
    first_line = text.splitlines()[0] if text.splitlines() else ""
    if first_line.count(";") > first_line.count(","):
        return ";"
    try:
        return csv.Sniffer().sniff(text[:2048], delimiters=",;").delimiter
    except csv.Error:
        return ","


def _normalize_header(value: str) -> str:
    return value.strip().lower().lstrip("\ufeff")


def _build_idempotency_key(normalized: dict[str, Any]) -> str:
    sale_external_id = normalized.get("sale_external_id")
    if sale_external_id:
        return str(sale_external_id)
    stable_parts = {
        "customer_external_id": normalized["customer_external_id"],
        "sale_date": normalized["sale_date"],
        "amount": normalized["gross_amount_minor"],
        "currency": normalized["currency"],
        "document_number": normalized.get("external_document_number"),
    }
    return f"generated:{_stable_hash(stable_parts)}"


class ImportService:
    async def preview_csv(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        created_by_user_id: UUID,
        filename: str | None,
        content: bytes,
    ) -> ImportBatch:
        self._validate_filename(filename)
        text = self._decode_csv(content)
        delimiter = _detect_delimiter(text)
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        if not reader.fieldnames:
            raise ValidationAppError("CSV file must include a header row.")

        columns = [_normalize_header(column) for column in reader.fieldnames]
        missing_columns = sorted(REQUIRED_COLUMNS.difference(columns))
        if missing_columns:
            raise ValidationAppError(
                "CSV file is missing required columns.",
                details={"missing_columns": missing_columns},
            )

        raw_rows = [
            {
                _normalize_header(key): value
                for key, value in row.items()
                if key is not None
            }
            for row in reader
        ]
        settings = get_settings()
        if len(raw_rows) > settings.import_max_rows:
            raise ValidationAppError(
                "CSV file exceeds the maximum allowed row count.",
                details={"max_rows": settings.import_max_rows},
            )

        row_results = [
            self._validate_row(row, row_number=index + 2)
            for index, row in enumerate(raw_rows)
        ]
        self._mark_duplicate_idempotency_keys(row_results)

        batch = ImportBatch(
            company_id=company_id,
            created_by_user_id=created_by_user_id,
            source_type="csv",
            provider="csv",
            status=ImportBatchStatus.PREVIEWED.value,
            original_filename=filename,
            total_rows=len(row_results),
            valid_rows=sum(1 for row in row_results if not row["errors"]),
            invalid_rows=sum(1 for row in row_results if row["errors"]),
            stats_json={
                "columns_detected": columns,
                "delimiter": delimiter,
                "duplicate_idempotency_policy": "invalid",
            },
        )
        session.add(batch)
        await session.flush()

        for row_result in row_results:
            import_row = ImportRow(
                company_id=company_id,
                import_batch_id=batch.id,
                row_number=row_result["row_number"],
                raw_row_json=row_result["raw_row_json"],
                normalized_row_json=row_result["normalized_row_json"],
                status=ImportRowStatus.INVALID.value
                if row_result["errors"]
                else ImportRowStatus.VALID.value,
                error_messages_json=row_result["errors"],
                idempotency_key=row_result["idempotency_key"],
                customer_external_id=row_result["customer_external_id"],
                sale_external_id=row_result["sale_external_id"],
            )
            session.add(import_row)

        await session.flush()
        return batch

    def _validate_filename(self, filename: str | None) -> None:
        if not filename:
            return
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if extension not in get_settings().import_allowed_extensions:
            raise ValidationAppError(
                "Import file extension is not allowed.",
                details={"extension": extension},
            )

    def _decode_csv(self, content: bytes) -> str:
        try:
            return content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValidationAppError("CSV file must be UTF-8 encoded.") from exc

    def _validate_row(self, raw_row: dict[str, Any], *, row_number: int) -> dict:
        errors: list[str] = []
        customer_external_id = _empty_to_none(raw_row.get("customer_external_id"))
        customer_name = _empty_to_none(raw_row.get("customer_name"))
        if customer_external_id is None:
            errors.append("customer_external_id is required.")
        if customer_name is None:
            errors.append("customer_name is required.")

        sale_date = _parse_date(raw_row.get("sale_date"), "sale_date", errors)
        effective_date = (
            _parse_date(raw_row.get("effective_date"), "effective_date", errors)
            if _empty_to_none(raw_row.get("effective_date")) is not None
            else sale_date
        )

        currency = self._parse_currency(raw_row.get("currency"), errors)
        currency_scale = _parse_int(
            raw_row.get("currency_scale"),
            "currency_scale",
            errors,
        )
        currency_scale = 0 if currency_scale is None else currency_scale
        if currency_scale < 0:
            errors.append("currency_scale must be non-negative.")
            currency_scale = 0

        amount_source = raw_row.get("gross_amount") or raw_row.get("amount")
        gross_amount_minor = _parse_amount_minor(
            amount_source,
            field="gross_amount" if raw_row.get("gross_amount") else "amount",
            currency_scale=currency_scale,
            errors=errors,
        )
        net_amount_minor = self._optional_amount(
            raw_row,
            "net_amount",
            currency_scale,
            errors,
        )
        vat_amount_minor = self._optional_amount(
            raw_row,
            "vat_amount",
            currency_scale,
            errors,
        )
        discount_amount_minor = self._optional_amount(
            raw_row,
            "discount_amount",
            currency_scale,
            errors,
        )
        paid_amount_minor = self._optional_amount(
            raw_row,
            "paid_amount",
            currency_scale,
            errors,
        )
        debt_amount_minor = self._optional_amount(
            raw_row,
            "debt_amount",
            currency_scale,
            errors,
        )

        document_kind = (_empty_to_none(raw_row.get("document_kind")) or "sale").lower()
        document_status = (
            _empty_to_none(raw_row.get("document_status")) or "posted"
        ).lower()
        payment_status = (
            _empty_to_none(raw_row.get("payment_status")) or "unknown"
        ).lower()
        self._validate_choice(document_kind, SaleDocumentKind, "document_kind", errors)
        self._validate_choice(
            document_status,
            SaleDocumentStatus,
            "document_status",
            errors,
        )
        self._validate_choice(payment_status, PaymentStatus, "payment_status", errors)

        amount_sign = _parse_int(raw_row.get("amount_sign"), "amount_sign", errors)
        if amount_sign is None:
            amount_sign = -1 if document_kind in {"return", "refund"} else 1
        if amount_sign not in {1, -1}:
            errors.append("amount_sign must be 1 or -1.")
        if document_kind in {"return", "refund"} and amount_sign != -1:
            errors.append("return/refund rows must use amount_sign -1.")
        if document_kind == "sale" and amount_sign != 1:
            errors.append("sale rows must use amount_sign 1.")

        sale_external_id = _empty_to_none(raw_row.get("sale_external_id"))
        document_number = _empty_to_none(raw_row.get("document_number"))
        metadata = _normalize_metadata(raw_row.get("metadata"), errors)

        normalized = {}
        if not errors:
            normalized = {
                "customer_external_id": customer_external_id,
                "customer_name": customer_name,
                "phone": _empty_to_none(raw_row.get("phone")),
                "email": _empty_to_none(raw_row.get("email")),
                "tax_id": _empty_to_none(raw_row.get("tax_id")),
                "metadata_json": metadata,
                "sale_external_id": sale_external_id,
                "sale_date": sale_date.isoformat() if sale_date else None,
                "effective_date": effective_date.isoformat()
                if effective_date
                else None,
                "document_kind": document_kind,
                "document_status": document_status,
                "payment_status": payment_status,
                "erp_document_type": _empty_to_none(raw_row.get("document_type")),
                "external_document_number": document_number,
                "gross_amount_minor": gross_amount_minor,
                "net_amount_minor": net_amount_minor,
                "vat_amount_minor": vat_amount_minor,
                "discount_amount_minor": discount_amount_minor,
                "paid_amount_minor": paid_amount_minor,
                "debt_amount_minor": debt_amount_minor,
                "amount_sign": amount_sign,
                "currency": currency,
                "currency_scale": currency_scale,
            }
            idempotency_key = _build_idempotency_key(normalized)
            normalized["idempotency_key"] = idempotency_key
            normalized["source_key"] = f"csv:{idempotency_key}"
            normalized["content_hash"] = _stable_hash(normalized)
        else:
            idempotency_key = sale_external_id

        return {
            "row_number": row_number,
            "raw_row_json": raw_row,
            "normalized_row_json": normalized,
            "errors": errors,
            "idempotency_key": idempotency_key,
            "customer_external_id": customer_external_id,
            "sale_external_id": sale_external_id,
        }

    def _parse_currency(self, value: Any, errors: list[str]) -> str | None:
        text = _empty_to_none(value)
        if text is None:
            errors.append("currency is required.")
            return None
        try:
            return normalize_currency(text)
        except ValueError:
            errors.append("currency must be a 3-letter ISO currency code.")
            return None

    def _optional_amount(
        self,
        raw_row: dict[str, Any],
        field: str,
        currency_scale: int,
        errors: list[str],
    ) -> int | None:
        if _empty_to_none(raw_row.get(field)) is None:
            return None
        return _parse_amount_minor(
            raw_row[field],
            field=field,
            currency_scale=currency_scale,
            errors=errors,
        )

    def _validate_choice(
        self,
        value: str,
        enum_cls,
        field: str,
        errors: list[str],
    ) -> None:
        if value not in {item.value for item in enum_cls}:
            errors.append(f"{field} has unsupported value.")

    def _mark_duplicate_idempotency_keys(self, row_results: list[dict]) -> None:
        keys = [
            row["idempotency_key"]
            for row in row_results
            if row["idempotency_key"] and not row["errors"]
        ]
        duplicates = {key for key, count in Counter(keys).items() if count > 1}
        if not duplicates:
            return
        for row in row_results:
            if row["idempotency_key"] in duplicates and not row["errors"]:
                row["errors"].append("duplicate idempotency_key inside import file.")
                row["normalized_row_json"] = {}

    async def commit_batch(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        import_batch_id: UUID,
        event_context: AuditContext | None = None,
    ) -> ImportBatch:
        batch = await self.get_batch(
            session,
            company_id=company_id,
            import_batch_id=import_batch_id,
        )
        if batch.status in {
            ImportBatchStatus.COMMITTED.value,
            ImportBatchStatus.CANCELLED.value,
            ImportBatchStatus.FAILED.value,
        }:
            raise ConflictError(
                "Import batch cannot be committed in its current status."
            )

        rows = await self._valid_rows(session, company_id=company_id, batch=batch)
        stats = {
            "created_customers": 0,
            "updated_customers": 0,
            "created_sales": 0,
            "updated_sales": 0,
            "skipped_sales": 0,
            "failed_rows": 0,
            "affected_customers": 0,
            "recalculated_progress_count": 0,
        }
        affected_customer_ids: set[UUID] = set()

        for row in rows:
            try:
                outcome = await self._commit_row(
                    session,
                    company_id=company_id,
                    batch=batch,
                    row=row,
                )
                stats["created_customers"] += int(outcome["created_customer"])
                stats["updated_customers"] += int(outcome["updated_customer"])
                stats["created_sales"] += int(outcome["created_sale"])
                stats["updated_sales"] += int(outcome["updated_sale"])
                stats["skipped_sales"] += int(outcome["skipped_sale"])
                if outcome["affected_customer_id"] is not None:
                    affected_customer_ids.add(outcome["affected_customer_id"])
                row.status = (
                    ImportRowStatus.SKIPPED.value
                    if outcome["skipped_sale"]
                    else ImportRowStatus.COMMITTED.value
                )
            except Exception as exc:
                row.status = ImportRowStatus.SKIPPED.value
                row.error_messages_json = [str(exc) or exc.__class__.__name__]
                stats["failed_rows"] += 1

        stats["affected_customers"] = len(affected_customer_ids)
        stats["recalculated_progress_count"] = await self._recalculate_progress(
            session,
            company_id=company_id,
            customer_ids=affected_customer_ids,
            event_context=event_context,
        )
        batch.status = ImportBatchStatus.COMMITTED.value
        batch.committed_at = utc_now()
        batch.committed_rows = stats["created_sales"] + stats["updated_sales"]
        batch.skipped_rows = stats["skipped_sales"] + stats["failed_rows"]
        batch.stats_json = {**(batch.stats_json or {}), "commit": stats}
        batch.error_summary = (
            "Import committed with skipped rows." if batch.skipped_rows else None
        )
        await domain_event_service.emit(
            session,
            company_id=company_id,
            event_type="import_committed",
            aggregate_type="import_batch",
            aggregate_id=batch.id,
            payload_json={
                "import_batch_id": str(batch.id),
                "status": batch.status,
                "committed_rows": batch.committed_rows,
                "skipped_rows": batch.skipped_rows,
                "stats": stats,
            },
            context=event_context,
        )
        await session.flush()
        return batch

    async def _valid_rows(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        batch: ImportBatch,
    ) -> list[ImportRow]:
        result = await session.execute(
            select(ImportRow)
            .where(
                ImportRow.company_id == company_id,
                ImportRow.import_batch_id == batch.id,
                ImportRow.status == ImportRowStatus.VALID.value,
            )
            .order_by(ImportRow.row_number.asc())
        )
        return list(result.scalars().all())

    async def _commit_row(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        batch: ImportBatch,
        row: ImportRow,
    ) -> dict[str, bool | UUID | None]:
        normalized = row.normalized_row_json
        customer, created_customer, updated_customer = await self._upsert_customer(
            session,
            company_id=company_id,
            normalized=normalized,
        )
        created_sale, updated_sale, skipped_sale = await self._upsert_sale_record(
            session,
            company_id=company_id,
            batch=batch,
            row=row,
            customer=customer,
            normalized=normalized,
        )
        return {
            "created_customer": created_customer,
            "updated_customer": updated_customer,
            "created_sale": created_sale,
            "updated_sale": updated_sale,
            "skipped_sale": skipped_sale,
            "affected_customer_id": None if skipped_sale else customer.id,
        }

    async def _upsert_customer(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        normalized: dict[str, Any],
    ) -> tuple[Customer, bool, bool]:
        result = await session.execute(
            select(CustomerExternalRef).where(
                CustomerExternalRef.company_id == company_id,
                CustomerExternalRef.provider == "csv",
                CustomerExternalRef.external_id == normalized["customer_external_id"],
            )
        )
        external_ref = result.scalar_one_or_none()
        if external_ref is None:
            customer = Customer(
                company_id=company_id,
                name=normalized["customer_name"],
                phone=normalized.get("phone"),
                email=self._normalized_email(normalized.get("email")),
                tax_id=normalized.get("tax_id"),
                status=CustomerStatus.ACTIVE.value,
                metadata_json=normalized.get("metadata_json") or {},
            )
            session.add(customer)
            await session.flush()
            external_ref = CustomerExternalRef(
                company_id=company_id,
                customer_id=customer.id,
                provider="csv",
                external_id=normalized["customer_external_id"],
                external_name=normalized["customer_name"],
                external_phone=normalized.get("phone"),
                external_email=self._normalized_email(normalized.get("email")),
                raw_payload_json={"metadata": normalized.get("metadata_json") or {}},
                last_seen_at=utc_now(),
            )
            session.add(external_ref)
            await session.flush()
            return customer, True, False

        customer = await session.get(Customer, external_ref.customer_id)
        if customer is None or customer.company_id != company_id:
            raise NotFoundError("Linked customer not found.")

        updated = False
        updates = {
            "name": normalized["customer_name"],
            "phone": normalized.get("phone"),
            "email": self._normalized_email(normalized.get("email")),
            "tax_id": normalized.get("tax_id"),
            "metadata_json": normalized.get("metadata_json") or {},
        }
        for field, value in updates.items():
            if value is not None and getattr(customer, field) != value:
                setattr(customer, field, value)
                updated = True

        external_ref.external_name = normalized["customer_name"]
        external_ref.external_phone = normalized.get("phone")
        external_ref.external_email = self._normalized_email(normalized.get("email"))
        external_ref.raw_payload_json = {
            "metadata": normalized.get("metadata_json") or {}
        }
        external_ref.last_seen_at = utc_now()
        await session.flush()
        return customer, False, updated

    def _normalized_email(self, value: str | None) -> str | None:
        return value.lower() if value else None

    async def _upsert_sale_record(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        batch: ImportBatch,
        row: ImportRow,
        customer: Customer,
        normalized: dict[str, Any],
    ) -> tuple[bool, bool, bool]:
        source_key = normalized["source_key"]
        result = await session.execute(
            select(SaleRecord).where(
                SaleRecord.company_id == company_id,
                SaleRecord.source_key == source_key,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            sale_record = SaleRecord(
                company_id=company_id,
                customer_id=customer.id,
                import_batch_id=batch.id,
                source_type="csv",
                source_key=source_key,
                provider="csv",
                erp_document_type=normalized.get("erp_document_type"),
                document_kind=normalized["document_kind"],
                external_document_id=normalized.get("sale_external_id"),
                external_document_number=normalized.get("external_document_number"),
                document_date=date.fromisoformat(normalized["sale_date"]),
                effective_date=date.fromisoformat(normalized["effective_date"]),
                gross_amount_minor=normalized["gross_amount_minor"],
                net_amount_minor=normalized.get("net_amount_minor"),
                vat_amount_minor=normalized.get("vat_amount_minor"),
                discount_amount_minor=normalized.get("discount_amount_minor"),
                paid_amount_minor=normalized.get("paid_amount_minor"),
                debt_amount_minor=normalized.get("debt_amount_minor"),
                amount_sign=normalized["amount_sign"],
                currency=normalized["currency"],
                currency_scale=normalized["currency_scale"],
                payment_status=normalized["payment_status"],
                document_status=normalized["document_status"],
                is_deleted_in_source=normalized["document_status"] == "deleted",
                is_archived_in_source=False,
                source_customer_external_id=normalized["customer_external_id"],
                raw_payload_json=row.raw_row_json,
                content_hash=normalized["content_hash"],
                synced_at=utc_now(),
            )
            session.add(sale_record)
            await session.flush()
            return True, False, False

        if existing.content_hash == normalized["content_hash"]:
            existing.synced_at = utc_now()
            await session.flush()
            return False, False, True

        for field, value in self._sale_update_values(
            batch=batch,
            row=row,
            customer=customer,
            normalized=normalized,
        ).items():
            setattr(existing, field, value)
        await session.flush()
        return False, True, False

    def _sale_update_values(
        self,
        *,
        batch: ImportBatch,
        row: ImportRow,
        customer: Customer,
        normalized: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "customer_id": customer.id,
            "import_batch_id": batch.id,
            "source_type": "csv",
            "provider": "csv",
            "erp_document_type": normalized.get("erp_document_type"),
            "document_kind": normalized["document_kind"],
            "external_document_id": normalized.get("sale_external_id"),
            "external_document_number": normalized.get("external_document_number"),
            "document_date": date.fromisoformat(normalized["sale_date"]),
            "effective_date": date.fromisoformat(normalized["effective_date"]),
            "gross_amount_minor": normalized["gross_amount_minor"],
            "net_amount_minor": normalized.get("net_amount_minor"),
            "vat_amount_minor": normalized.get("vat_amount_minor"),
            "discount_amount_minor": normalized.get("discount_amount_minor"),
            "paid_amount_minor": normalized.get("paid_amount_minor"),
            "debt_amount_minor": normalized.get("debt_amount_minor"),
            "amount_sign": normalized["amount_sign"],
            "currency": normalized["currency"],
            "currency_scale": normalized["currency_scale"],
            "payment_status": normalized["payment_status"],
            "document_status": normalized["document_status"],
            "is_deleted_in_source": normalized["document_status"] == "deleted",
            "is_archived_in_source": False,
            "source_customer_external_id": normalized["customer_external_id"],
            "raw_payload_json": row.raw_row_json,
            "content_hash": normalized["content_hash"],
            "synced_at": utc_now(),
        }

    async def _recalculate_progress(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        customer_ids: set[UUID],
        event_context: AuditContext | None = None,
    ) -> int:
        if not customer_ids:
            return 0
        result = await session.execute(
            select(Campaign.id).where(
                Campaign.company_id == company_id,
                Campaign.status == CampaignStatus.ACTIVE.value,
                Campaign.deleted_at.is_(None),
            )
        )
        recalculated_count = 0
        for campaign_id in result.scalars().all():
            stats = await progress_service.recalculate_affected_customers(
                session,
                company_id=company_id,
                campaign_id=campaign_id,
                customer_ids=list(customer_ids),
                event_context=event_context,
            )
            recalculated_count += stats.recalculated_count
        return recalculated_count

    async def cancel_batch(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        import_batch_id: UUID,
    ) -> ImportBatch:
        batch = await self.get_batch(
            session,
            company_id=company_id,
            import_batch_id=import_batch_id,
        )
        if batch.status == ImportBatchStatus.COMMITTED.value:
            raise ConflictError("Committed import batches cannot be cancelled.")
        if batch.status != ImportBatchStatus.CANCELLED.value:
            batch.status = ImportBatchStatus.CANCELLED.value
        await session.flush()
        return batch

    async def list_batches(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        pagination: PaginationParams,
        status: str | None = None,
        created_at_from: datetime | None = None,
        created_at_to: datetime | None = None,
    ) -> tuple[list[ImportBatch], int]:
        filters = [ImportBatch.company_id == company_id]
        if status is not None:
            filters.append(ImportBatch.status == status)
        if created_at_from is not None:
            filters.append(ImportBatch.created_at >= created_at_from)
        if created_at_to is not None:
            filters.append(ImportBatch.created_at <= created_at_to)

        base_query: Select[tuple[ImportBatch]] = select(ImportBatch).where(*filters)
        total_result = await session.execute(
            select(func.count()).select_from(
                select(ImportBatch.id).where(*filters).subquery()
            )
        )
        result = await session.execute(
            base_query.order_by(ImportBatch.created_at.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        return list(result.scalars().all()), int(total_result.scalar_one())

    async def get_batch(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        import_batch_id: UUID,
    ) -> ImportBatch:
        result = await session.execute(
            select(ImportBatch).where(
                ImportBatch.id == import_batch_id,
                ImportBatch.company_id == company_id,
            )
        )
        batch = result.scalar_one_or_none()
        if batch is None:
            raise NotFoundError("Import batch not found.")
        return batch

    async def list_rows(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        import_batch_id: UUID,
        pagination: PaginationParams,
        status: str | None = None,
    ) -> tuple[list[ImportRow], int]:
        await self.get_batch(
            session,
            company_id=company_id,
            import_batch_id=import_batch_id,
        )
        filters = [
            ImportRow.company_id == company_id,
            ImportRow.import_batch_id == import_batch_id,
        ]
        if status is not None:
            filters.append(ImportRow.status == status)

        total_result = await session.execute(
            select(func.count()).select_from(
                select(ImportRow.id).where(*filters).subquery()
            )
        )
        result = await session.execute(
            select(ImportRow)
            .where(*filters)
            .order_by(ImportRow.row_number.asc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        return list(result.scalars().all()), int(total_result.scalar_one())

    async def preview_errors(
        self,
        session: AsyncSession,
        *,
        batch: ImportBatch,
    ) -> list[ImportRow]:
        result = await session.execute(
            select(ImportRow)
            .where(
                ImportRow.import_batch_id == batch.id,
                ImportRow.status == ImportRowStatus.INVALID.value,
            )
            .order_by(ImportRow.row_number.asc())
            .limit(get_settings().import_preview_error_limit)
        )
        return list(result.scalars().all())


import_service = ImportService()
