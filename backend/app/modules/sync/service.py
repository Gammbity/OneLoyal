from collections.abc import Iterable
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.datetime import ensure_timezone_aware, utc_now
from app.common.pagination import PaginationParams
from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.modules.campaigns.models import Campaign, CampaignStatus
from app.modules.customers.models import (
    Customer,
    CustomerExternalRef,
    CustomerStatus,
)
from app.modules.integrations.models import Integration, IntegrationStatus
from app.modules.integrations.providers.base import (
    ERPCustomerDTO,
    ERPSaleDTO,
    ProviderFetchResult,
)
from app.modules.integrations.service import integration_service
from app.modules.progress.service import progress_service
from app.modules.sales.models import (
    PaymentStatus,
    SaleDocumentKind,
    SaleDocumentStatus,
    SaleRecord,
)
from app.modules.sync.models import (
    SyncError,
    SyncErrorEntityType,
    SyncErrorSeverity,
    SyncRun,
    SyncRunStatus,
    SyncType,
)


def _empty_stats() -> dict[str, Any]:
    return {
        "fetched_customers": 0,
        "created_customers": 0,
        "updated_customers": 0,
        "fetched_sales": 0,
        "created_sales": 0,
        "updated_sales": 0,
        "skipped_sales": 0,
        "failed_records": 0,
        "affected_customers": 0,
        "recalculated_progress_count": 0,
    }


def _source_key(provider: str, sale: ERPSaleDTO) -> str:
    if sale.source_key:
        return sale.source_key.strip()
    return f"{provider}:{sale.external_id}"


def _valid_sale_values(sale: ERPSaleDTO) -> None:
    if sale.document_kind not in {item.value for item in SaleDocumentKind}:
        raise ValidationAppError(
            "Unsupported sale document kind.",
            details={"document_kind": sale.document_kind},
        )
    if sale.payment_status not in {item.value for item in PaymentStatus}:
        raise ValidationAppError(
            "Unsupported payment status.",
            details={"payment_status": sale.payment_status},
        )
    if sale.document_status not in {item.value for item in SaleDocumentStatus}:
        raise ValidationAppError(
            "Unsupported document status.",
            details={"document_status": sale.document_status},
        )
    if sale.document_kind in {
        SaleDocumentKind.RETURN.value,
        SaleDocumentKind.REFUND.value,
    } and sale.amount_sign != -1:
        raise ValidationAppError(
            "Returns and refunds must use amount_sign -1.",
            details={"amount_sign": sale.amount_sign},
        )
    if sale.document_kind == SaleDocumentKind.SALE.value and sale.amount_sign != 1:
        raise ValidationAppError(
            "Sale documents must use amount_sign 1.",
            details={"amount_sign": sale.amount_sign},
        )


def _external_updated_is_newer(existing: SaleRecord, sale: ERPSaleDTO) -> bool:
    if sale.external_updated_at is None:
        return False
    if existing.external_updated_at is None:
        return True
    return ensure_timezone_aware(sale.external_updated_at) > ensure_timezone_aware(
        existing.external_updated_at
    )


class SyncService:
    async def sync_integration(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        integration_id: UUID,
        created_by_user_id: UUID | None,
        sync_type: str = SyncType.MANUAL.value,
    ) -> SyncRun:
        integration = await integration_service.get_integration(
            session,
            company_id=company_id,
            integration_id=integration_id,
        )
        if integration.status == IntegrationStatus.DISABLED.value:
            raise ConflictError("Disabled integrations cannot be synced.")
        await self._ensure_no_running_sync(
            session,
            company_id=company_id,
            integration_id=integration_id,
        )

        now = utc_now()
        stats = _empty_stats()
        sync_run = SyncRun(
            company_id=company_id,
            integration_id=integration_id,
            sync_type=sync_type,
            status=SyncRunStatus.RUNNING.value,
            started_at=now,
            cursor_before_json=integration.sync_cursor_json or {},
            cursor_after_json={},
            stats_json=stats,
            created_by_user_id=created_by_user_id,
        )
        integration.last_attempted_sync_at = now
        session.add(sync_run)
        await session.flush()

        try:
            provider = await integration_service.build_provider(
                session,
                integration=integration,
            )
            connection = await provider.test_connection()
            if not connection.ok:
                await self._add_sync_error(
                    session,
                    company_id=company_id,
                    sync_run=sync_run,
                    entity_type=SyncErrorEntityType.PROVIDER.value,
                    external_id=None,
                    error_code="connection_failed",
                    message=connection.message,
                    raw_payload_json=connection.details,
                )
                stats["failed_records"] += 1
                self._finish_run(
                    sync_run,
                    integration=integration,
                    status=SyncRunStatus.FAILED.value,
                    stats=stats,
                    error_summary=connection.message,
                )
                integration.status = IntegrationStatus.ERROR.value
                await session.flush()
                return sync_run

            cursor_before = integration.sync_cursor_json or {}
            customer_result = ProviderFetchResult[ERPCustomerDTO](items=[])
            if getattr(provider, "supports_customers", True):
                customer_result = await self._sync_customers_from_provider(
                    session,
                    company_id=company_id,
                    integration=integration,
                    sync_run=sync_run,
                    provider=provider,
                    cursor=self._provider_cursor(cursor_before, "customers"),
                    stats=stats,
                )
            else:
                stats["customers_not_supported"] = True

            sale_result = ProviderFetchResult[ERPSaleDTO](items=[])
            affected_customer_ids: set[UUID] = set()
            if getattr(provider, "supports_sales", True):
                sale_result, affected_customer_ids = (
                    await self._sync_sales_from_provider(
                        session,
                        company_id=company_id,
                        integration=integration,
                        sync_run=sync_run,
                        provider=provider,
                        cursor=self._provider_cursor(cursor_before, "sales"),
                        stats=stats,
                    )
                )
            else:
                stats["sales_not_supported"] = True

            stats["affected_customers"] = len(affected_customer_ids)
            await self._recalculate_progress(
                session,
                company_id=company_id,
                sync_run=sync_run,
                customer_ids=affected_customer_ids,
                stats=stats,
            )

            cursor_after = {
                "customers": customer_result.next_cursor,
                "sales": sale_result.next_cursor,
            }
            status = (
                SyncRunStatus.PARTIALLY_FAILED.value
                if stats["failed_records"] > 0
                else SyncRunStatus.SUCCESS.value
            )
            self._finish_run(
                sync_run,
                integration=integration,
                status=status,
                stats=stats,
                cursor_after=cursor_after,
                error_summary=None
                if status == SyncRunStatus.SUCCESS.value
                else "Sync completed with row-level errors.",
            )
            if status == SyncRunStatus.SUCCESS.value:
                integration.last_successful_sync_at = sync_run.finished_at
                integration.sync_cursor_json = cursor_after
                integration.status = IntegrationStatus.ACTIVE.value
            await session.flush()
            return sync_run
        except Exception as exc:
            await self._record_row_error(
                session,
                company_id=company_id,
                sync_run=sync_run,
                entity_type=SyncErrorEntityType.PROVIDER.value,
                external_id=None,
                exc=exc,
                raw_payload_json={},
            )
            stats["failed_records"] += 1
            self._finish_run(
                sync_run,
                integration=integration,
                status=SyncRunStatus.FAILED.value,
                stats=stats,
                error_summary=str(exc),
            )
            integration.status = IntegrationStatus.ERROR.value
            await session.flush()
            return sync_run

    def _provider_cursor(
        self,
        cursor_state: dict[str, Any],
        section: str,
    ) -> dict[str, Any]:
        section_cursor = cursor_state.get(section)
        if isinstance(section_cursor, dict):
            return section_cursor
        return {}

    async def _sync_customers_from_provider(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        integration: Integration,
        sync_run: SyncRun,
        provider: Any,
        cursor: dict[str, Any],
        stats: dict[str, Any],
    ) -> ProviderFetchResult[ERPCustomerDTO]:
        current_cursor: dict[str, Any] | None = cursor
        last_result = ProviderFetchResult[ERPCustomerDTO](items=[])
        while current_cursor is not None:
            last_result = await provider.fetch_customers(cursor=current_cursor)
            stats["fetched_customers"] += len(last_result.items)
            for customer in last_result.items:
                try:
                    created, updated = await self._upsert_customer(
                        session,
                        company_id=company_id,
                        integration=integration,
                        customer_dto=customer,
                    )
                    stats["created_customers"] += int(created)
                    stats["updated_customers"] += int(updated)
                except Exception as exc:
                    await self._record_row_error(
                        session,
                        company_id=company_id,
                        sync_run=sync_run,
                        entity_type=SyncErrorEntityType.CUSTOMER.value,
                        external_id=customer.external_id,
                        exc=exc,
                        raw_payload_json=customer.raw_payload,
                    )
                    stats["failed_records"] += 1

            if not last_result.has_more:
                break
            current_cursor = last_result.next_cursor
            if current_cursor is None:
                break

        return last_result

    async def _sync_sales_from_provider(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        integration: Integration,
        sync_run: SyncRun,
        provider: Any,
        cursor: dict[str, Any],
        stats: dict[str, Any],
    ) -> tuple[ProviderFetchResult[ERPSaleDTO], set[UUID]]:
        current_cursor: dict[str, Any] | None = cursor
        last_result = ProviderFetchResult[ERPSaleDTO](items=[])
        affected_customer_ids: set[UUID] = set()
        while current_cursor is not None:
            last_result = await provider.fetch_sales(cursor=current_cursor)
            stats["fetched_sales"] += len(last_result.items)
            for sale in last_result.items:
                try:
                    outcome = await self._upsert_sale_record(
                        session,
                        company_id=company_id,
                        integration=integration,
                        sale_dto=sale,
                    )
                    stats["created_sales"] += int(outcome["created"])
                    stats["updated_sales"] += int(outcome["updated"])
                    stats["skipped_sales"] += int(outcome["skipped"])
                    if outcome["affected_customer_id"] is not None:
                        affected_customer_ids.add(outcome["affected_customer_id"])
                except Exception as exc:
                    await self._record_row_error(
                        session,
                        company_id=company_id,
                        sync_run=sync_run,
                        entity_type=SyncErrorEntityType.SALE_RECORD.value,
                        external_id=sale.external_id,
                        exc=exc,
                        raw_payload_json=sale.raw_payload,
                    )
                    stats["failed_records"] += 1
                    stats["skipped_sales"] += 1

            if not last_result.has_more:
                break
            current_cursor = last_result.next_cursor
            if current_cursor is None:
                break

        return last_result, affected_customer_ids

    async def _ensure_no_running_sync(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        integration_id: UUID,
    ) -> None:
        result = await session.execute(
            select(SyncRun.id).where(
                SyncRun.company_id == company_id,
                SyncRun.integration_id == integration_id,
                SyncRun.status == SyncRunStatus.RUNNING.value,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise ConflictError("A sync is already running for this integration.")

    async def _upsert_customer(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        integration: Integration,
        customer_dto: ERPCustomerDTO,
    ) -> tuple[bool, bool]:
        result = await session.execute(
            select(CustomerExternalRef).where(
                CustomerExternalRef.company_id == company_id,
                CustomerExternalRef.provider == integration.provider,
                CustomerExternalRef.external_id == customer_dto.external_id,
            )
        )
        external_ref = result.scalar_one_or_none()
        if external_ref is None:
            customer = Customer(
                company_id=company_id,
                name=customer_dto.name.strip(),
                phone=customer_dto.phone,
                email=str(customer_dto.email).lower()
                if customer_dto.email is not None
                else None,
                tax_id=customer_dto.tax_id,
                status=CustomerStatus.ACTIVE.value,
                metadata_json=customer_dto.metadata,
            )
            session.add(customer)
            await session.flush()
            external_ref = CustomerExternalRef(
                company_id=company_id,
                customer_id=customer.id,
                integration_id=integration.id,
                provider=integration.provider,
                external_id=customer_dto.external_id,
                external_name=customer_dto.name,
                external_phone=customer_dto.phone,
                external_email=str(customer_dto.email).lower()
                if customer_dto.email is not None
                else None,
                raw_payload_json=customer_dto.raw_payload,
                last_seen_at=customer_dto.last_seen_at or utc_now(),
            )
            session.add(external_ref)
            await session.flush()
            return True, False

        customer = await session.get(Customer, external_ref.customer_id)
        if customer is None or customer.company_id != company_id:
            raise NotFoundError("Linked customer not found.")

        updated = False
        updates = {
            "name": customer_dto.name.strip(),
            "phone": customer_dto.phone,
            "email": str(customer_dto.email).lower()
            if customer_dto.email is not None
            else None,
            "tax_id": customer_dto.tax_id,
            "metadata_json": customer_dto.metadata,
        }
        for field, value in updates.items():
            if getattr(customer, field) != value:
                setattr(customer, field, value)
                updated = True

        ref_updates = {
            "integration_id": integration.id,
            "external_name": customer_dto.name,
            "external_phone": customer_dto.phone,
            "external_email": str(customer_dto.email).lower()
            if customer_dto.email is not None
            else None,
            "raw_payload_json": customer_dto.raw_payload,
        }
        for field, value in ref_updates.items():
            if getattr(external_ref, field) != value:
                setattr(external_ref, field, value)
                updated = True
        external_ref.last_seen_at = customer_dto.last_seen_at or utc_now()

        await session.flush()
        return False, updated

    async def _upsert_sale_record(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        integration: Integration,
        sale_dto: ERPSaleDTO,
    ) -> dict[str, bool | UUID | None]:
        _valid_sale_values(sale_dto)
        external_ref = await self._external_ref_for_sale(
            session,
            company_id=company_id,
            provider=integration.provider,
            customer_external_id=sale_dto.customer_external_id,
        )
        source_key = _source_key(integration.provider, sale_dto)
        result = await session.execute(
            select(SaleRecord).where(
                SaleRecord.company_id == company_id,
                SaleRecord.source_key == source_key,
            )
        )
        existing = result.scalar_one_or_none()
        now = utc_now()
        if existing is None:
            sale_record = SaleRecord(
                company_id=company_id,
                customer_id=external_ref.customer_id,
                integration_id=integration.id,
                source_type="erp",
                source_key=source_key,
                provider=integration.provider,
                erp_document_type=sale_dto.erp_document_type,
                document_kind=sale_dto.document_kind,
                external_document_id=sale_dto.external_id,
                external_document_number=sale_dto.external_document_number,
                external_updated_at=sale_dto.external_updated_at,
                document_date=sale_dto.document_date,
                effective_date=sale_dto.effective_date,
                gross_amount_minor=sale_dto.gross_amount_minor,
                net_amount_minor=sale_dto.net_amount_minor,
                vat_amount_minor=sale_dto.vat_amount_minor,
                discount_amount_minor=sale_dto.discount_amount_minor,
                paid_amount_minor=sale_dto.paid_amount_minor,
                debt_amount_minor=sale_dto.debt_amount_minor,
                amount_sign=sale_dto.amount_sign,
                currency=sale_dto.currency,
                currency_scale=sale_dto.currency_scale,
                payment_status=sale_dto.payment_status,
                document_status=sale_dto.document_status,
                is_deleted_in_source=sale_dto.is_deleted_in_source,
                is_archived_in_source=sale_dto.is_archived_in_source,
                source_customer_external_id=sale_dto.customer_external_id,
                raw_payload_json=sale_dto.raw_payload,
                content_hash=sale_dto.content_hash,
                synced_at=now,
            )
            session.add(sale_record)
            await session.flush()
            return {
                "created": True,
                "updated": False,
                "skipped": False,
                "affected_customer_id": external_ref.customer_id,
            }

        should_update = (
            existing.content_hash != sale_dto.content_hash
            or _external_updated_is_newer(existing, sale_dto)
        )
        if not should_update:
            existing.synced_at = now
            await session.flush()
            return {
                "created": False,
                "updated": False,
                "skipped": False,
                "affected_customer_id": None,
            }

        updates = self._sale_update_values(
            integration=integration,
            sale_dto=sale_dto,
            customer_id=external_ref.customer_id,
            source_key=source_key,
            synced_at=now,
        )
        for field, value in updates.items():
            setattr(existing, field, value)
        await session.flush()
        return {
            "created": False,
            "updated": True,
            "skipped": False,
            "affected_customer_id": external_ref.customer_id,
        }

    async def _external_ref_for_sale(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        provider: str,
        customer_external_id: str,
    ) -> CustomerExternalRef:
        result = await session.execute(
            select(CustomerExternalRef).where(
                CustomerExternalRef.company_id == company_id,
                CustomerExternalRef.provider == provider,
                CustomerExternalRef.external_id == customer_external_id,
            )
        )
        external_ref = result.scalar_one_or_none()
        if external_ref is None:
            raise NotFoundError(
                "Sale customer external reference was not found.",
                details={"customer_external_id": customer_external_id},
            )
        return external_ref

    def _sale_update_values(
        self,
        *,
        integration: Integration,
        sale_dto: ERPSaleDTO,
        customer_id: UUID,
        source_key: str,
        synced_at: datetime,
    ) -> dict[str, Any]:
        return {
            "customer_id": customer_id,
            "integration_id": integration.id,
            "source_type": "erp",
            "source_key": source_key,
            "provider": integration.provider,
            "erp_document_type": sale_dto.erp_document_type,
            "document_kind": sale_dto.document_kind,
            "external_document_id": sale_dto.external_id,
            "external_document_number": sale_dto.external_document_number,
            "external_updated_at": sale_dto.external_updated_at,
            "document_date": sale_dto.document_date,
            "effective_date": sale_dto.effective_date,
            "gross_amount_minor": sale_dto.gross_amount_minor,
            "net_amount_minor": sale_dto.net_amount_minor,
            "vat_amount_minor": sale_dto.vat_amount_minor,
            "discount_amount_minor": sale_dto.discount_amount_minor,
            "paid_amount_minor": sale_dto.paid_amount_minor,
            "debt_amount_minor": sale_dto.debt_amount_minor,
            "amount_sign": sale_dto.amount_sign,
            "currency": sale_dto.currency,
            "currency_scale": sale_dto.currency_scale,
            "payment_status": sale_dto.payment_status,
            "document_status": sale_dto.document_status,
            "is_deleted_in_source": sale_dto.is_deleted_in_source,
            "is_archived_in_source": sale_dto.is_archived_in_source,
            "source_customer_external_id": sale_dto.customer_external_id,
            "raw_payload_json": sale_dto.raw_payload,
            "content_hash": sale_dto.content_hash,
            "synced_at": synced_at,
        }

    async def _recalculate_progress(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        sync_run: SyncRun,
        customer_ids: Iterable[UUID],
        stats: dict[str, Any],
    ) -> None:
        customer_ids_list = list(customer_ids)
        if not customer_ids_list:
            return

        result = await session.execute(
            select(Campaign.id).where(
                Campaign.company_id == company_id,
                Campaign.status == CampaignStatus.ACTIVE.value,
                Campaign.deleted_at.is_(None),
            )
        )
        campaign_ids = list(result.scalars().all())
        for campaign_id in campaign_ids:
            try:
                recalculation = await progress_service.recalculate_affected_customers(
                    session,
                    company_id=company_id,
                    campaign_id=campaign_id,
                    customer_ids=customer_ids_list,
                )
                stats["recalculated_progress_count"] += (
                    recalculation.recalculated_count
                )
                stats["failed_records"] += recalculation.failed_count
            except Exception as exc:
                await self._record_row_error(
                    session,
                    company_id=company_id,
                    sync_run=sync_run,
                    entity_type=SyncErrorEntityType.PROGRESS.value,
                    external_id=str(campaign_id),
                    exc=exc,
                    raw_payload_json={"campaign_id": str(campaign_id)},
                )
                stats["failed_records"] += 1

    async def _record_row_error(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        sync_run: SyncRun,
        entity_type: str,
        external_id: str | None,
        exc: Exception,
        raw_payload_json: dict[str, Any],
    ) -> None:
        if isinstance(exc, ValidationAppError):
            error_code = exc.code
            message = exc.message
        elif isinstance(exc, NotFoundError):
            error_code = exc.code
            message = exc.message
        else:
            error_code = exc.__class__.__name__.lower()
            message = str(exc) or exc.__class__.__name__
        await self._add_sync_error(
            session,
            company_id=company_id,
            sync_run=sync_run,
            entity_type=entity_type,
            external_id=external_id,
            error_code=error_code,
            message=message,
            raw_payload_json=raw_payload_json,
        )

    async def _add_sync_error(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        sync_run: SyncRun,
        entity_type: str,
        external_id: str | None,
        error_code: str,
        message: str,
        raw_payload_json: dict[str, Any],
    ) -> SyncError:
        sync_error = SyncError(
            company_id=company_id,
            sync_run_id=sync_run.id,
            entity_type=entity_type,
            external_id=external_id,
            severity=SyncErrorSeverity.ERROR.value,
            error_code=error_code,
            message=message,
            raw_payload_json=raw_payload_json,
        )
        session.add(sync_error)
        await session.flush()
        return sync_error

    def _finish_run(
        self,
        sync_run: SyncRun,
        *,
        integration: Integration,
        status: str,
        stats: dict[str, Any],
        cursor_after: dict[str, Any] | None = None,
        error_summary: str | None,
    ) -> None:
        finished_at = utc_now()
        sync_run.status = status
        sync_run.finished_at = finished_at
        sync_run.cursor_after_json = cursor_after or {}
        sync_run.stats_json = stats
        sync_run.error_summary = error_summary
        integration.last_attempted_sync_at = sync_run.started_at

    async def list_sync_runs(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        pagination: PaginationParams,
        integration_id: UUID | None = None,
        status: str | None = None,
        sync_type: str | None = None,
        started_at_from: datetime | None = None,
        started_at_to: datetime | None = None,
    ) -> tuple[list[SyncRun], int]:
        filters = [SyncRun.company_id == company_id]
        if integration_id is not None:
            filters.append(SyncRun.integration_id == integration_id)
        if status is not None:
            filters.append(SyncRun.status == status)
        if sync_type is not None:
            filters.append(SyncRun.sync_type == sync_type)
        if started_at_from is not None:
            filters.append(SyncRun.started_at >= started_at_from)
        if started_at_to is not None:
            filters.append(SyncRun.started_at <= started_at_to)

        base_query: Select[tuple[SyncRun]] = select(SyncRun).where(*filters)
        total_result = await session.execute(
            select(func.count()).select_from(select(SyncRun.id).where(*filters).subquery())
        )
        result = await session.execute(
            base_query.order_by(SyncRun.started_at.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        return list(result.scalars().all()), int(total_result.scalar_one())

    async def get_sync_run(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        sync_run_id: UUID,
    ) -> SyncRun:
        result = await session.execute(
            select(SyncRun).where(
                SyncRun.id == sync_run_id,
                SyncRun.company_id == company_id,
            )
        )
        sync_run = result.scalar_one_or_none()
        if sync_run is None:
            raise NotFoundError("Sync run not found.")
        return sync_run

    async def list_sync_errors(
        self,
        session: AsyncSession,
        *,
        company_id: UUID,
        sync_run_id: UUID,
        pagination: PaginationParams,
    ) -> tuple[list[SyncError], int]:
        await self.get_sync_run(
            session,
            company_id=company_id,
            sync_run_id=sync_run_id,
        )
        filters = [
            SyncError.company_id == company_id,
            SyncError.sync_run_id == sync_run_id,
        ]
        total_result = await session.execute(
            select(func.count()).select_from(
                select(SyncError.id).where(*filters).subquery()
            )
        )
        result = await session.execute(
            select(SyncError)
            .where(*filters)
            .order_by(SyncError.created_at.desc())
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        return list(result.scalars().all()), int(total_result.scalar_one())


sync_service = SyncService()
