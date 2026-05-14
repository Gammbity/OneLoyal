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
from app.modules.integrations.providers.odoo.client import OdooClient
from app.modules.integrations.providers.odoo.errors import (
    OdooAPIError,
    OdooCredentialsError,
)
from app.modules.integrations.providers.odoo.mapper import (
    map_invoice_to_sale,
    map_partner_to_customer,
)

PARTNER_FIELDS = [
    "id",
    "name",
    "phone",
    "mobile",
    "email",
    "vat",
    "ref",
    "is_company",
    "active",
    "country_id",
    "lang",
    "write_date",
]

INVOICE_FIELDS = [
    "id",
    "name",
    "partner_id",
    "invoice_date",
    "date",
    "create_date",
    "write_date",
    "amount_total",
    "amount_untaxed",
    "amount_tax",
    "amount_residual",
    "currency_id",
    "state",
    "payment_state",
    "move_type",
    "active",
]


class OdooProvider:
    provider_name = "odoo"
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
        try:
            async with self._client() as client:
                await client.execute_kw(
                    model="res.partner",
                    method="search_count",
                    args=[[]],
                )
        except OdooCredentialsError as exc:
            return ProviderConnectionResult(
                ok=False,
                message=str(exc) or "Odoo credentials are missing.",
                details={"reason": "missing_credentials"},
            )
        except OdooAPIError as exc:
            return ProviderConnectionResult(
                ok=False, message=exc.message, details=exc.details
            )
        except Exception as exc:
            return ProviderConnectionResult(
                ok=False,
                message="Odoo connection test failed.",
                details={"error": exc.__class__.__name__},
            )
        return ProviderConnectionResult(
            ok=True,
            message="Odoo connection succeeded.",
            details={"provider": self.provider_name},
        )

    async def fetch_customers(
        self,
        cursor: Mapping[str, Any] | None = None,
    ) -> ProviderFetchResult[ERPCustomerDTO]:
        offset, limit = self._page(cursor)
        domain = self._customer_domain()
        async with self._client() as client:
            rows = await client.search_read(
                model="res.partner",
                domain=domain,
                fields=PARTNER_FIELDS,
                offset=offset,
                limit=limit,
                order="id asc",
            )

        customers: list[ERPCustomerDTO] = []
        errors: list[ProviderRowError] = []
        skipped = 0
        for row in rows:
            if not isinstance(row, dict):
                skipped += 1
                continue
            try:
                customers.append(map_partner_to_customer(row))
            except (ValueError, ValidationError) as exc:
                skipped += 1
                errors.append(
                    ProviderRowError(
                        external_id=str(row.get("id")) if row.get("id") else None,
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
        domain = self._sales_domain(
            start_date=start_date or self._settings_date("sales_start_date"),
            end_date=end_date or self._settings_date("sales_end_date"),
        )
        async with self._client() as client:
            rows = await client.search_read(
                model="account.move",
                domain=domain,
                fields=INVOICE_FIELDS,
                offset=offset,
                limit=limit,
                order="id asc",
            )

        default_currency = str(self.settings.get("default_currency") or "UZS")
        currency_scale = self.settings.get("currency_scale")
        scale = int(currency_scale) if isinstance(currency_scale, int) else None

        sales: list[ERPSaleDTO] = []
        errors: list[ProviderRowError] = []
        for row in rows:
            if not isinstance(row, dict):
                errors.append(
                    ProviderRowError(
                        external_id=None,
                        error_code="mapping_error",
                        message="Odoo invoice row is not an object.",
                        raw_payload={},
                    )
                )
                continue
            try:
                sales.append(
                    map_invoice_to_sale(
                        row,
                        default_currency=default_currency,
                        currency_scale=scale,
                    )
                )
            except (ValueError, ValidationError) as exc:
                errors.append(
                    ProviderRowError(
                        external_id=str(row.get("id")) if row.get("id") else None,
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
                "offset": offset,
                "limit": limit,
                "domain": domain,
            },
            errors=errors,
        )

    def _page(self, cursor: Mapping[str, Any] | None) -> tuple[int, int]:
        settings = get_settings()
        data = dict(cursor or {})
        offset = max(int(data.get("offset", 0) or 0), 0)
        limit = int(self.settings.get("page_limit") or settings.odoo_page_limit)
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

    def _customer_domain(self) -> list[Any]:
        domain: list[Any] = []
        if self.settings.get("only_companies") is True:
            domain.append(["is_company", "=", True])
        if self.settings.get("only_customers", True):
            domain.append(["customer_rank", ">", 0])
        return domain

    def _sales_domain(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
    ) -> list[Any]:
        move_types = self.settings.get("move_types") or ["out_invoice", "out_refund"]
        domain: list[Any] = [
            ["move_type", "in", list(move_types)],
            ["state", "=", "posted"],
        ]
        if start_date is not None:
            domain.append(["invoice_date", ">=", start_date.isoformat()])
        if end_date is not None:
            domain.append(["invoice_date", "<=", end_date.isoformat()])
        return domain

    def _client(self) -> OdooClient:
        return OdooClient(
            credentials=self.credentials,
            base_url=self.settings.get("base_url"),
            database=self.settings.get("database"),
            timeout_seconds=self.settings.get("timeout_seconds"),
            max_retries=self.settings.get("max_retries"),
        )
