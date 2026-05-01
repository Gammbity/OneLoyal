import hashlib
import json
from collections.abc import Mapping
from datetime import date
from typing import Any

from pydantic import ValidationError

from app.modules.integrations.models import Integration
from app.modules.integrations.providers.base import (
    ERPCustomerDTO,
    ERPSaleDTO,
    ProviderConnectionResult,
    ProviderFetchResult,
)


def _stable_content_hash(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class FakeProvider:
    provider_name = "fake"

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
        if self.settings.get("fail_connection") is True:
            return ProviderConnectionResult(
                ok=False,
                message="Fake provider connection failed by configuration.",
                details={"reason": "fail_connection"},
            )
        try:
            self._customers()
            self._sales()
        except ValidationError as exc:
            return ProviderConnectionResult(
                ok=False,
                message="Fake provider settings are invalid.",
                details={"errors": exc.errors()},
            )
        return ProviderConnectionResult(
            ok=True,
            message="Fake provider connection succeeded.",
            details={"provider": self.provider_name},
        )

    async def fetch_customers(
        self,
        cursor: Mapping[str, Any] | None = None,
    ) -> ProviderFetchResult[ERPCustomerDTO]:
        if self.settings.get("raise_fetch_error") == "customers":
            raise RuntimeError("Fake customer fetch failed by configuration.")
        return ProviderFetchResult(
            items=self._customers(),
            next_cursor=None,
            has_more=False,
            stats={"source": "settings_json", "cursor": dict(cursor or {})},
        )

    async def fetch_sales(
        self,
        cursor: Mapping[str, Any] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> ProviderFetchResult[ERPSaleDTO]:
        if self.settings.get("raise_fetch_error") == "sales":
            raise RuntimeError("Fake sale fetch failed by configuration.")

        sales = self._sales()
        if start_date is not None:
            sales = [sale for sale in sales if sale.effective_date >= start_date]
        if end_date is not None:
            sales = [sale for sale in sales if sale.effective_date <= end_date]

        return ProviderFetchResult(
            items=sales,
            next_cursor=None,
            has_more=False,
            stats={"source": "settings_json", "cursor": dict(cursor or {})},
        )

    def _customers(self) -> list[ERPCustomerDTO]:
        return [
            ERPCustomerDTO.model_validate(
                {
                    "metadata": {},
                    "raw_payload": raw_customer,
                    **raw_customer,
                }
            )
            for raw_customer in self.settings.get("customers", [])
        ]

    def _sales(self) -> list[ERPSaleDTO]:
        sales: list[ERPSaleDTO] = []
        for raw_sale in self.settings.get("sales", []):
            payload = {
                "amount_sign": 1,
                "currency_scale": 0,
                "payment_status": "unknown",
                "document_status": "unknown",
                "raw_payload": raw_sale,
                **raw_sale,
            }
            payload["content_hash"] = payload.get("content_hash") or (
                _stable_content_hash(raw_sale)
            )
            sales.append(ERPSaleDTO.model_validate(payload))
        return sales
