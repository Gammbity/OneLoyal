from collections.abc import Mapping
from datetime import date
from typing import Any

from pydantic import ValidationError

from app.core.settings import get_settings
from app.modules.integrations.models import Integration
from app.modules.integrations.providers.base import (
    ERPCustomerDTO,
    ERPSaleDTO,
    ProviderConnectionResult,
    ProviderFetchResult,
    ProviderRowError,
)
from app.modules.integrations.providers.one_c.client import OneCClient
from app.modules.integrations.providers.one_c.errors import (
    OneCAPIError,
    OneCCredentialsError,
)
from app.modules.integrations.providers.one_c.mapper import (
    map_counterparty_to_customer,
    map_document_to_sale,
)

DEFAULT_CUSTOMER_ENTITY = "Catalog_Контрагенты"
DEFAULT_SALE_ENTITY = "Document_РеализацияТоваровУслуг"


class OneCProvider:
    provider_name = "one_c"
    supports_customers = True
    supports_sales = True

    def __init__(
        self,
        *,
        integration: Integration,
        credentials: dict[str, Any],
        settings: dict[str, Any],
    ) -> None:
        self.integration = integration
        self.credentials = credentials
        self.settings = settings

    async def test_connection(self) -> ProviderConnectionResult:
        entity = self._customer_entity()
        try:
            async with self._client() as client:
                await client.list_entity(entity=entity, offset=0, limit=1)
        except OneCCredentialsError as exc:
            return ProviderConnectionResult(
                ok=False,
                message=str(exc) or "1C credentials are missing.",
                details={"reason": "missing_credentials"},
            )
        except OneCAPIError as exc:
            return ProviderConnectionResult(
                ok=False, message=exc.message, details=exc.details
            )
        except Exception as exc:
            return ProviderConnectionResult(
                ok=False,
                message="1C connection test failed.",
                details={"error": exc.__class__.__name__},
            )
        return ProviderConnectionResult(
            ok=True,
            message="1C connection succeeded.",
            details={"provider": self.provider_name, "entity": entity},
        )

    async def fetch_customers(
        self,
        cursor: Mapping[str, Any] | None = None,
    ) -> ProviderFetchResult[ERPCustomerDTO]:
        offset, limit = self._page(cursor)
        entity = self._customer_entity()
        filter_expr = self._customer_filter()
        field_map = self._field_map("customer_field_map")

        async with self._client() as client:
            rows = await client.list_entity(
                entity=entity,
                offset=offset,
                limit=limit,
                filter_expr=filter_expr,
            )

        customers: list[ERPCustomerDTO] = []
        errors: list[ProviderRowError] = []
        skipped = 0
        for row in rows:
            if not isinstance(row, dict):
                skipped += 1
                continue
            try:
                customers.append(
                    map_counterparty_to_customer(row, field_map=field_map)
                )
            except (ValueError, ValidationError) as exc:
                skipped += 1
                errors.append(
                    ProviderRowError(
                        external_id=row.get("Ref_Key"),
                        error_code="mapping_error",
                        message=str(exc),
                        raw_payload=row,
                    )
                )

        page_size = len(rows)
        has_more = page_size >= limit
        next_cursor = {"offset": offset + page_size} if has_more else None
        return ProviderFetchResult(
            items=customers,
            next_cursor=next_cursor,
            has_more=has_more,
            stats={
                "fetched_rows": page_size,
                "mapped_customers": len(customers),
                "skipped_rows": skipped,
                "entity": entity,
                "offset": offset,
                "limit": limit,
            },
            errors=errors,
        )

    async def fetch_sales(
        self,
        cursor: Mapping[str, Any] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> ProviderFetchResult[ERPSaleDTO]:
        offset, limit = self._page(cursor)
        entity = self._sale_entity()
        filter_expr = self._sale_filter(
            start_date=start_date or self._settings_date("sales_start_date"),
            end_date=end_date or self._settings_date("sales_end_date"),
        )
        field_map = self._field_map("sale_field_map")
        erp_document_type = self.settings.get("erp_document_type") or entity
        default_currency = str(self.settings.get("default_currency") or "UZS")
        currency_scale = self.settings.get("currency_scale")
        scale = int(currency_scale) if isinstance(currency_scale, int) else None

        async with self._client() as client:
            rows = await client.list_entity(
                entity=entity,
                offset=offset,
                limit=limit,
                filter_expr=filter_expr,
                order_by="Date",
            )

        sales: list[ERPSaleDTO] = []
        errors: list[ProviderRowError] = []
        for row in rows:
            if not isinstance(row, dict):
                errors.append(
                    ProviderRowError(
                        external_id=None,
                        error_code="mapping_error",
                        message="1C document row is not an object.",
                        raw_payload={},
                    )
                )
                continue
            try:
                sales.append(
                    map_document_to_sale(
                        row,
                        default_currency=default_currency,
                        currency_scale=scale,
                        field_map=field_map,
                        erp_document_type=erp_document_type,
                    )
                )
            except (ValueError, ValidationError) as exc:
                errors.append(
                    ProviderRowError(
                        external_id=row.get("Ref_Key"),
                        error_code="mapping_error",
                        message=str(exc),
                        raw_payload=row,
                    )
                )

        page_size = len(rows)
        has_more = page_size >= limit
        next_cursor = {"offset": offset + page_size} if has_more else None
        return ProviderFetchResult(
            items=sales,
            next_cursor=next_cursor,
            has_more=has_more,
            stats={
                "fetched_rows": page_size,
                "mapped_sales": len(sales),
                "skipped_rows": len(errors),
                "entity": entity,
                "offset": offset,
                "limit": limit,
                "filter": filter_expr,
            },
            errors=errors,
        )

    def _page(self, cursor: Mapping[str, Any] | None) -> tuple[int, int]:
        settings = get_settings()
        data = dict(cursor or {})
        offset = max(int(data.get("offset", 0) or 0), 0)
        limit = int(self.settings.get("page_limit") or settings.one_c_page_limit)
        limit = max(1, min(limit, 1000))
        return offset, limit

    def _settings_date(self, key: str) -> date | None:
        raw = self.settings.get(key)
        if not isinstance(raw, str) or not raw.strip():
            return None
        try:
            return date.fromisoformat(raw.strip())
        except ValueError:
            return None

    def _field_map(self, key: str) -> dict[str, Any] | None:
        value = self.settings.get(key)
        return value if isinstance(value, dict) else None

    def _customer_entity(self) -> str:
        value = self.settings.get("customer_entity")
        if isinstance(value, str) and value.strip():
            return value.strip()
        return DEFAULT_CUSTOMER_ENTITY

    def _sale_entity(self) -> str:
        value = self.settings.get("sale_entity")
        if isinstance(value, str) and value.strip():
            return value.strip()
        return DEFAULT_SALE_ENTITY

    def _customer_filter(self) -> str | None:
        clauses: list[str] = []
        if self.settings.get("exclude_deleted", True):
            clauses.append("DeletionMark eq false")
        extra = self.settings.get("customer_filter")
        if isinstance(extra, str) and extra.strip():
            clauses.append(f"({extra.strip()})")
        return " and ".join(clauses) if clauses else None

    def _sale_filter(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
    ) -> str | None:
        clauses: list[str] = []
        if self.settings.get("posted_only", True):
            clauses.append("Posted eq true")
        if self.settings.get("exclude_deleted", True):
            clauses.append("DeletionMark eq false")
        if start_date is not None:
            clauses.append(f"Date ge datetime'{start_date.isoformat()}T00:00:00'")
        if end_date is not None:
            clauses.append(f"Date le datetime'{end_date.isoformat()}T23:59:59'")
        extra = self.settings.get("sale_filter")
        if isinstance(extra, str) and extra.strip():
            clauses.append(f"({extra.strip()})")
        return " and ".join(clauses) if clauses else None

    def _client(self) -> OneCClient:
        return OneCClient(
            credentials=self.credentials,
            base_url=self.settings.get("base_url"),
            timeout_seconds=self.settings.get("timeout_seconds"),
            max_retries=self.settings.get("max_retries"),
        )
