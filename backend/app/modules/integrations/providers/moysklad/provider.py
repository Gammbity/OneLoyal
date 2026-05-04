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
)
from app.modules.integrations.providers.moysklad.client import MoySkladClient
from app.modules.integrations.providers.moysklad.errors import (
    MoySkladAPIError,
    MoySkladCredentialsError,
)
from app.modules.integrations.providers.moysklad.mapper import (
    map_counterparty_to_customer,
)


class MoySkladProvider:
    provider_name = "moysklad"
    supports_customers = True
    supports_sales = False

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
                payload = await client.list_counterparties(offset=0, limit=1)
        except MoySkladCredentialsError:
            return ProviderConnectionResult(
                ok=False,
                message="MoySklad credentials are missing.",
                details={"reason": "missing_credentials"},
            )
        except MoySkladAPIError as exc:
            return ProviderConnectionResult(
                ok=False,
                message=exc.message,
                details=exc.details,
            )
        except Exception as exc:
            return ProviderConnectionResult(
                ok=False,
                message="MoySklad connection test failed.",
                details={"error": exc.__class__.__name__},
            )

        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        return ProviderConnectionResult(
            ok=True,
            message="MoySklad connection succeeded.",
            details={
                "provider": self.provider_name,
                "counterparty_count": meta.get("size"),
            },
        )

    async def fetch_customers(
        self,
        cursor: Mapping[str, Any] | None = None,
    ) -> ProviderFetchResult[ERPCustomerDTO]:
        settings = get_settings()
        cursor_data = dict(cursor or {})
        offset = max(int(cursor_data.get("offset", 0) or 0), 0)
        limit = int(self.settings.get("page_limit") or settings.moysklad_page_limit)
        limit = max(1, min(limit, 1000))

        async with self._client() as client:
            payload = await client.list_counterparties(offset=offset, limit=limit)

        rows = payload.get("rows")
        if not isinstance(rows, list):
            rows = []

        customers: list[ERPCustomerDTO] = []
        skipped_rows = 0
        for row in rows:
            if not isinstance(row, dict):
                skipped_rows += 1
                continue
            try:
                customers.append(map_counterparty_to_customer(row))
            except (ValueError, ValidationError):
                skipped_rows += 1

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
                "skipped_rows": skipped_rows,
                "offset": offset,
                "limit": limit,
            },
        )

    async def fetch_sales(
        self,
        cursor: Mapping[str, Any] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> ProviderFetchResult[ERPSaleDTO]:
        return ProviderFetchResult(
            items=[],
            next_cursor=None,
            has_more=False,
            stats={"not_supported": True},
        )

    def _client(self) -> MoySkladClient:
        return MoySkladClient(
            credentials=self.credentials,
            base_url=self.settings.get("base_url"),
            timeout_seconds=self.settings.get("timeout_seconds"),
            max_retries=self.settings.get("max_retries"),
        )
