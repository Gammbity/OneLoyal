import asyncio
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.modules.customers.models import Customer, CustomerExternalRef
from app.modules.integrations.models import Integration, IntegrationCredential
from app.modules.integrations.providers.moysklad.client import MoySkladClient
from app.modules.integrations.providers.moysklad.errors import MoySkladAPIError
from app.modules.integrations.providers.moysklad.mapper import (
    extract_uuid_from_meta,
    map_demand_to_sale,
)
from app.modules.integrations.providers.moysklad.provider import MoySkladProvider
from app.modules.integrations.providers.registry import provider_registry
from app.modules.sync.service import sync_service


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_company(
    client: TestClient,
    *,
    slug: str = "moysklad-company",
    owner_email: str = "moysklad-owner@example.com",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/register-company",
        json={
            "company_name": f"{slug.title()} LLC",
            "company_slug": slug,
            "owner_full_name": "Owner User",
            "owner_email": owner_email,
            "owner_password": "super-secret-password",
        },
    )
    assert response.status_code == 201, response.json()
    return response.json()


def create_moysklad_integration(
    client: TestClient,
    *,
    token: str,
    settings_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/integrations",
        headers=auth_headers(token),
        json={
            "provider": "moysklad",
            "name": "MoySklad",
            "settings_json": settings_json or {},
            "credentials_json": {
                "username": "moysklad-user",
                "password": "moysklad-secret",
            },
        },
    )
    assert response.status_code == 201, response.json()
    return response.json()


def counterparty_payload(
    external_id: str = "counterparty-1",
    *,
    name: str = "MoySklad Customer",
    archived: bool = False,
) -> dict[str, Any]:
    return {
        "id": external_id,
        "name": name,
        "phone": "+998901234567",
        "email": "customer@example.com",
        "inn": "123456789",
        "code": "C-1",
        "externalCode": "EXT-1",
        "archived": archived,
        "tags": ["vip"],
        "updated": "2026-01-10 12:30:45",
        "companyType": "legal",
    }


def demand_payload(
    external_id: str = "demand-1",
    *,
    counterparty_id: str = "counterparty-1",
    amount: int = 30_000_000,
    payed_sum: int | None = 30_000_000,
    applicable: bool | None = True,
    moment: str = "2026-06-15 10:30:00",
    updated: str = "2026-06-15 11:00:00",
    name: str = "00001",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": external_id,
        "updated": updated,
        "name": name,
        "moment": moment,
        "sum": amount,
        "agent": {
            "meta": {
                "href": (
                    "https://api.moysklad.ru/api/remap/1.2/entity/"
                    f"counterparty/{counterparty_id}"
                ),
                "type": "counterparty",
                "mediaType": "application/json",
            }
        },
        "rate": {"currency": {"isoCode": "UZS"}},
    }
    if payed_sum is not None:
        payload["payedSum"] = payed_sum
    if applicable is not None:
        payload["applicable"] = applicable
    return payload


def dummy_integration() -> Integration:
    return Integration(
        id=uuid4(),
        company_id=uuid4(),
        provider="moysklad",
        name="MoySklad",
        settings_json={},
        sync_cursor_json={},
    )


def create_active_campaign(client: TestClient, *, token: str) -> dict[str, Any]:
    campaign_response = client.post(
        "/api/v1/campaigns",
        headers=auth_headers(token),
        json={
            "title": "MoySklad Campaign",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "currency": "UZS",
        },
    )
    assert campaign_response.status_code == 201, campaign_response.json()
    campaign = campaign_response.json()
    tier_response = client.post(
        f"/api/v1/campaigns/{campaign['id']}/gift-tiers",
        headers=auth_headers(token),
        json={"title": "Powerbank", "required_amount_minor": 10_000_000},
    )
    assert tier_response.status_code == 201, tier_response.json()
    activate_response = client.post(
        f"/api/v1/campaigns/{campaign['id']}/activate",
        headers=auth_headers(token),
    )
    assert activate_response.status_code == 200, activate_response.json()
    return activate_response.json()


def queue_and_execute_sync(
    client: TestClient,
    *,
    token: str,
    integration_id: str,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/integrations/{integration_id}/sync",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.json()
    queued = response.json()
    assert queued["status"] == "queued"
    assert queued["task_id"]
    SessionLocal = client.app.state.test_sessionmaker

    async def execute_sync() -> None:
        async with SessionLocal() as session:
            await sync_service.execute_sync_run(
                session,
                sync_run_id=UUID(queued["sync_run_id"]),
                use_redis_lock=False,
            )
            await session.commit()

    asyncio.run(execute_sync())
    sync_run_response = client.get(
        f"/api/v1/sync-runs/{queued['sync_run_id']}",
        headers=auth_headers(token),
    )
    assert sync_run_response.status_code == 200, sync_run_response.json()
    return sync_run_response.json()


def test_moysklad_provider_is_registered() -> None:
    assert "moysklad" in provider_registry.supported_providers()


def test_moysklad_client_success_and_basic_auth() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"meta": {"size": 0, "limit": 1, "offset": 0}, "rows": []},
        )

    async def run() -> dict[str, Any]:
        transport = httpx.MockTransport(handler)
        async with MoySkladClient(
            credentials={"username": "user", "password": "secret"},
            base_url="https://example.test/api/remap/1.2",
            max_retries=0,
            transport=transport,
        ) as client:
            return await client.list_counterparties(offset=0, limit=1)

    payload = asyncio.run(run())

    assert payload["rows"] == []
    assert requests[0].url.path == "/api/remap/1.2/entity/counterparty"
    assert requests[0].url.params["offset"] == "0"
    assert requests[0].url.params["limit"] == "1"
    assert requests[0].headers["authorization"].startswith("Basic ")
    assert requests[0].headers["accept-encoding"] == "gzip"


def test_moysklad_client_lists_demands_with_filters() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"meta": {"size": 0, "limit": 10, "offset": 20}, "rows": []},
        )

    async def run() -> dict[str, Any]:
        transport = httpx.MockTransport(handler)
        async with MoySkladClient(
            credentials={"username": "user", "password": "secret"},
            base_url="https://example.test/api/remap/1.2",
            max_retries=0,
            transport=transport,
        ) as client:
            return await client.list_demands(
                offset=20,
                limit=10,
                filters=[
                    "moment>=2026-01-01 00:00:00",
                    "moment<=2026-12-31 23:59:59",
                ],
            )

    payload = asyncio.run(run())

    assert payload["rows"] == []
    assert requests[0].url.path == "/api/remap/1.2/entity/demand"
    assert requests[0].url.params["offset"] == "20"
    assert requests[0].url.params["limit"] == "10"
    assert requests[0].url.params["filter"] == (
        "moment>=2026-01-01 00:00:00;moment<=2026-12-31 23:59:59"
    )


@pytest.mark.parametrize("status_code", [401, 429, 500])
def test_moysklad_client_error_statuses_are_sanitized(status_code: int) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            headers={"X-Lognex-Retry-After": "0"},
            json={
                "errors": [
                    {
                        "code": 1073,
                        "error": "Failure",
                        "error_message": "A public provider error.",
                    }
                ]
            },
        )

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with MoySkladClient(
            credentials={"username": "user", "password": "secret"},
            base_url="https://example.test/api/remap/1.2",
            max_retries=0,
            transport=transport,
        ) as client:
            await client.list_counterparties(offset=0, limit=1)

    with pytest.raises(MoySkladAPIError) as error:
        asyncio.run(run())

    assert error.value.status_code == status_code
    assert "secret" not in str(error.value.details)


def test_moysklad_provider_missing_credentials_returns_connection_failure() -> None:
    provider = MoySkladProvider(
        integration=dummy_integration(),
        credentials={},
        settings={},
    )

    result = asyncio.run(provider.test_connection())

    assert result.ok is False
    assert result.details["reason"] == "missing_credentials"


def test_moysklad_fetch_customers_maps_counterparties(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_list_counterparties(
        self: MoySkladClient,
        *,
        offset: int,
        limit: int,
    ) -> dict[str, Any]:
        assert offset == 0
        assert limit == 1
        return {
            "meta": {"size": 2, "limit": 1, "offset": 0},
            "rows": [counterparty_payload(archived=True)],
        }

    monkeypatch.setattr(
        MoySkladClient,
        "list_counterparties",
        fake_list_counterparties,
    )
    provider = MoySkladProvider(
        integration=dummy_integration(),
        credentials={"username": "user", "password": "secret"},
        settings={"page_limit": 1},
    )

    result = asyncio.run(provider.fetch_customers(cursor={}))

    assert result.has_more is True
    assert result.next_cursor == {"offset": 1}
    assert len(result.items) == 1
    customer = result.items[0]
    assert customer.external_id == "counterparty-1"
    assert customer.name == "MoySklad Customer"
    assert customer.phone == "+998901234567"
    assert str(customer.email) == "customer@example.com"
    assert customer.tax_id == "123456789"
    assert customer.metadata["archived"] is True
    assert customer.metadata["code"] == "C-1"
    assert customer.raw_payload["externalCode"] == "EXT-1"
    assert customer.last_seen_at is not None


def test_moysklad_demand_maps_to_sale_dto() -> None:
    sale = map_demand_to_sale(
        demand_payload(payed_sum=12_000_000),
        default_currency="UZS",
    )

    assert sale.external_id == "demand-1"
    assert sale.customer_external_id == "counterparty-1"
    assert sale.document_kind == "sale"
    assert sale.amount_sign == 1
    assert sale.erp_document_type == "demand"
    assert sale.external_document_number == "00001"
    assert sale.document_date.isoformat() == "2026-06-15"
    assert sale.effective_date.isoformat() == "2026-06-15"
    assert sale.gross_amount_minor == 30_000_000
    assert sale.paid_amount_minor == 12_000_000
    assert sale.debt_amount_minor == 18_000_000
    assert sale.payment_status == "partial"
    assert sale.document_status == "posted"
    assert sale.currency == "UZS"
    assert sale.currency_scale == 0
    assert sale.external_updated_at is not None
    assert sale.content_hash


def test_moysklad_demand_mapper_handles_status_and_missing_optional_fields() -> None:
    cancelled_sale = map_demand_to_sale(
        demand_payload(applicable=False, payed_sum=0),
        default_currency="UZS",
    )
    unknown_payment_sale = map_demand_to_sale(
        demand_payload(payed_sum=None, applicable=None),
        default_currency="UZS",
    )

    assert cancelled_sale.document_status == "cancelled"
    assert cancelled_sale.payment_status == "unpaid"
    assert cancelled_sale.paid_amount_minor == 0
    assert unknown_payment_sale.document_status == "unknown"
    assert unknown_payment_sale.payment_status == "unknown"
    assert unknown_payment_sale.paid_amount_minor is None


def test_moysklad_counterparty_id_extracts_from_meta_href() -> None:
    assert (
        extract_uuid_from_meta(
            {
                "meta": {
                    "href": (
                        "https://api.moysklad.ru/api/remap/1.2/entity/"
                        "counterparty/850efc5f-f504-11e5-8a84-bae500000161"
                    )
                }
            },
            entity_type="counterparty",
        )
        == "850efc5f-f504-11e5-8a84-bae500000161"
    )


def test_moysklad_fetch_sales_maps_demands_and_row_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_list_demands(
        self: MoySkladClient,
        *,
        offset: int,
        limit: int,
        filters: list[str] | None = None,
    ) -> dict[str, Any]:
        assert offset == 0
        assert limit == 2
        assert filters == ["moment>=2026-01-01 00:00:00"]
        invalid_demand = demand_payload("bad-demand")
        invalid_demand.pop("agent")
        return {
            "meta": {"size": 2, "limit": 2, "offset": 0},
            "rows": [demand_payload("demand-1"), invalid_demand],
        }

    monkeypatch.setattr(MoySkladClient, "list_demands", fake_list_demands)
    provider = MoySkladProvider(
        integration=dummy_integration(),
        credentials={"username": "user", "password": "secret"},
        settings={"page_limit": 2, "sales_start_date": "2026-01-01"},
    )

    result = asyncio.run(provider.fetch_sales(cursor={}))

    assert result.has_more is True
    assert result.next_cursor == {"offset": 2}
    assert len(result.items) == 1
    assert result.items[0].external_id == "demand-1"
    assert len(result.errors) == 1
    assert result.errors[0].external_id == "bad-demand"
    assert result.errors[0].error_code == "mapping_error"


def test_moysklad_integration_create_test_and_customer_only_sync(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def page(offset: int) -> list[dict[str, Any]]:
        if offset == 0:
            return [counterparty_payload("counterparty-1", name="First Customer")]
        if offset == 1:
            return [counterparty_payload("counterparty-2", name="Second Customer")]
        return []

    async def fake_list_counterparties(
        self: MoySkladClient,
        *,
        offset: int,
        limit: int,
    ) -> dict[str, Any]:
        return {
            "meta": {"size": len(page(offset)), "limit": limit, "offset": offset},
            "rows": page(offset),
        }

    async def fake_list_demands(
        self: MoySkladClient,
        *,
        offset: int,
        limit: int,
        filters: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "meta": {"size": 0, "limit": limit, "offset": offset},
            "rows": [],
        }

    monkeypatch.setattr(
        MoySkladClient,
        "list_counterparties",
        fake_list_counterparties,
    )
    monkeypatch.setattr(MoySkladClient, "list_demands", fake_list_demands)
    owner = register_company(client)
    integration = create_moysklad_integration(
        client,
        token=owner["access_token"],
        settings_json={"page_limit": 1},
    )

    test_response = client.post(
        f"/api/v1/integrations/{integration['id']}/test",
        headers=auth_headers(owner["access_token"]),
    )
    sync_run = queue_and_execute_sync(
        client,
        token=owner["access_token"],
        integration_id=integration["id"],
    )
    second_sync_run = queue_and_execute_sync(
        client,
        token=owner["access_token"],
        integration_id=integration["id"],
    )
    customers_response = client.get(
        "/api/v1/customers",
        headers=auth_headers(owner["access_token"]),
    )

    assert test_response.status_code == 200, test_response.json()
    assert test_response.json()["ok"] is True
    assert sync_run["status"] == "success"
    assert sync_run["stats_json"]["fetched_customers"] == 2
    assert sync_run["stats_json"]["created_customers"] == 2
    assert sync_run["stats_json"]["fetched_sales"] == 0
    assert "sales_not_supported" not in sync_run["stats_json"]
    assert sync_run["stats_json"]["recalculated_progress_count"] == 0
    assert second_sync_run["stats_json"]["created_customers"] == 0
    assert second_sync_run["stats_json"]["updated_customers"] == 0
    customers = customers_response.json()
    assert customers["pagination"]["total"] == 2
    assert {item["name"] for item in customers["items"]} == {
        "First Customer",
        "Second Customer",
    }


def test_moysklad_sync_creates_external_refs_and_keeps_credentials_hidden(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_list_counterparties(
        self: MoySkladClient,
        *,
        offset: int,
        limit: int,
    ) -> dict[str, Any]:
        if offset > 0:
            return {"meta": {"size": 0, "limit": limit, "offset": offset}, "rows": []}
        return {
            "meta": {"size": 1, "limit": limit, "offset": offset},
            "rows": [counterparty_payload()],
        }

    async def fake_list_demands(
        self: MoySkladClient,
        *,
        offset: int,
        limit: int,
        filters: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "meta": {"size": 0, "limit": limit, "offset": offset},
            "rows": [],
        }

    monkeypatch.setattr(
        MoySkladClient,
        "list_counterparties",
        fake_list_counterparties,
    )
    monkeypatch.setattr(MoySkladClient, "list_demands", fake_list_demands)
    owner = register_company(client)
    integration = create_moysklad_integration(client, token=owner["access_token"])
    SessionLocal = client.app.state.test_sessionmaker

    sync_run = queue_and_execute_sync(
        client,
        token=owner["access_token"],
        integration_id=integration["id"],
    )

    async def load_records() -> tuple[str, Customer, CustomerExternalRef]:
        async with SessionLocal() as session:
            credential_result = await session.execute(
                select(IntegrationCredential).where(
                    IntegrationCredential.integration_id == UUID(integration["id"])
                )
            )
            customer_result = await session.execute(select(Customer))
            ref_result = await session.execute(select(CustomerExternalRef))
            credential = credential_result.scalar_one()
            return (
                credential.encrypted_credentials,
                customer_result.scalar_one(),
                ref_result.scalar_one(),
            )

    encrypted_credentials, customer, external_ref = asyncio.run(load_records())

    assert sync_run["status"] == "success"
    assert integration["has_active_credentials"] is True
    assert "credentials_json" not in integration
    assert "encrypted_credentials" not in integration
    assert "moysklad-secret" not in encrypted_credentials
    assert customer.name == "MoySklad Customer"
    assert external_ref.provider == "moysklad"
    assert external_ref.external_id == "counterparty-1"


def test_moysklad_sync_creates_sales_and_recalculates_progress(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_list_counterparties(
        self: MoySkladClient,
        *,
        offset: int,
        limit: int,
    ) -> dict[str, Any]:
        if offset > 0:
            return {"meta": {"size": 0, "limit": limit, "offset": offset}, "rows": []}
        return {
            "meta": {"size": 1, "limit": limit, "offset": offset},
            "rows": [counterparty_payload()],
        }

    async def fake_list_demands(
        self: MoySkladClient,
        *,
        offset: int,
        limit: int,
        filters: list[str] | None = None,
    ) -> dict[str, Any]:
        if offset > 0:
            return {"meta": {"size": 0, "limit": limit, "offset": offset}, "rows": []}
        return {
            "meta": {"size": 1, "limit": limit, "offset": offset},
            "rows": [demand_payload(amount=35_000_000, payed_sum=35_000_000)],
        }

    monkeypatch.setattr(
        MoySkladClient,
        "list_counterparties",
        fake_list_counterparties,
    )
    monkeypatch.setattr(MoySkladClient, "list_demands", fake_list_demands)
    owner = register_company(client)
    campaign = create_active_campaign(client, token=owner["access_token"])
    integration = create_moysklad_integration(client, token=owner["access_token"])

    sync_run = queue_and_execute_sync(
        client,
        token=owner["access_token"],
        integration_id=integration["id"],
    )
    sales_response = client.get(
        "/api/v1/sale-records",
        headers=auth_headers(owner["access_token"]),
    )
    customers_response = client.get(
        "/api/v1/customers",
        headers=auth_headers(owner["access_token"]),
    )
    customer = customers_response.json()["items"][0]
    progress_response = client.get(
        f"/api/v1/progress/campaigns/{campaign['id']}/customers/{customer['id']}",
        headers=auth_headers(owner["access_token"]),
    )

    assert sync_run["status"] == "success"
    assert sync_run["stats_json"]["created_sales"] == 1
    assert sync_run["stats_json"]["recalculated_progress_count"] == 1
    sale = sales_response.json()["items"][0]
    assert sale["source_key"] == "moysklad:demand-1"
    assert sale["erp_document_type"] == "demand"
    assert sale["external_document_number"] == "00001"
    assert sale["gross_amount_minor"] == 35_000_000
    assert sale["paid_amount_minor"] == 35_000_000
    assert sale["debt_amount_minor"] == 0
    assert sale["payment_status"] == "paid"
    assert sale["document_status"] == "posted"
    assert progress_response.status_code == 200
    assert progress_response.json()["total_amount_minor"] == 35_000_000


def test_moysklad_sync_is_idempotent_and_changed_demand_updates_sale(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"amount": 30_000_000, "updated": "2026-06-15 11:00:00"}

    async def fake_list_counterparties(
        self: MoySkladClient,
        *,
        offset: int,
        limit: int,
    ) -> dict[str, Any]:
        if offset > 0:
            return {"meta": {"size": 0, "limit": limit, "offset": offset}, "rows": []}
        return {
            "meta": {"size": 1, "limit": limit, "offset": offset},
            "rows": [counterparty_payload()],
        }

    async def fake_list_demands(
        self: MoySkladClient,
        *,
        offset: int,
        limit: int,
        filters: list[str] | None = None,
    ) -> dict[str, Any]:
        if offset > 0:
            return {"meta": {"size": 0, "limit": limit, "offset": offset}, "rows": []}
        return {
            "meta": {"size": 1, "limit": limit, "offset": offset},
            "rows": [
                demand_payload(
                    amount=state["amount"],
                    updated=state["updated"],
                )
            ],
        }

    monkeypatch.setattr(
        MoySkladClient,
        "list_counterparties",
        fake_list_counterparties,
    )
    monkeypatch.setattr(MoySkladClient, "list_demands", fake_list_demands)
    owner = register_company(client)
    integration = create_moysklad_integration(client, token=owner["access_token"])

    first_sync = queue_and_execute_sync(
        client,
        token=owner["access_token"],
        integration_id=integration["id"],
    )
    second_sync = queue_and_execute_sync(
        client,
        token=owner["access_token"],
        integration_id=integration["id"],
    )
    state["amount"] = 40_000_000
    state["updated"] = "2026-06-15 12:00:00"
    third_sync = queue_and_execute_sync(
        client,
        token=owner["access_token"],
        integration_id=integration["id"],
    )
    sales_response = client.get(
        "/api/v1/sale-records",
        headers=auth_headers(owner["access_token"]),
    )

    assert first_sync["stats_json"]["created_sales"] == 1
    assert second_sync["stats_json"]["created_sales"] == 0
    assert second_sync["stats_json"]["updated_sales"] == 0
    assert third_sync["stats_json"]["updated_sales"] == 1
    sales = sales_response.json()
    assert sales["pagination"]["total"] == 1
    assert sales["items"][0]["gross_amount_minor"] == 40_000_000


def test_moysklad_missing_sale_customer_ref_creates_sync_error(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_list_counterparties(
        self: MoySkladClient,
        *,
        offset: int,
        limit: int,
    ) -> dict[str, Any]:
        return {
            "meta": {"size": 0, "limit": limit, "offset": offset},
            "rows": [],
        }

    async def fake_list_demands(
        self: MoySkladClient,
        *,
        offset: int,
        limit: int,
        filters: list[str] | None = None,
    ) -> dict[str, Any]:
        if offset > 0:
            return {"meta": {"size": 0, "limit": limit, "offset": offset}, "rows": []}
        return {
            "meta": {"size": 1, "limit": limit, "offset": offset},
            "rows": [demand_payload(counterparty_id="missing-customer")],
        }

    monkeypatch.setattr(
        MoySkladClient,
        "list_counterparties",
        fake_list_counterparties,
    )
    monkeypatch.setattr(MoySkladClient, "list_demands", fake_list_demands)
    owner = register_company(client)
    integration = create_moysklad_integration(client, token=owner["access_token"])

    sync_run = queue_and_execute_sync(
        client,
        token=owner["access_token"],
        integration_id=integration["id"],
    )
    errors_response = client.get(
        f"/api/v1/sync-runs/{sync_run['id']}/errors",
        headers=auth_headers(owner["access_token"]),
    )

    assert sync_run["status"] == "partially_failed"
    assert sync_run["stats_json"]["skipped_sales"] == 1
    assert errors_response.status_code == 200, errors_response.json()
    errors = errors_response.json()["items"]
    assert len(errors) == 1
    assert errors[0]["entity_type"] == "sale_record"
    assert errors[0]["external_id"] == "demand-1"


def test_moysklad_mapping_error_creates_sync_error(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_list_counterparties(
        self: MoySkladClient,
        *,
        offset: int,
        limit: int,
    ) -> dict[str, Any]:
        return {
            "meta": {"size": 0, "limit": limit, "offset": offset},
            "rows": [],
        }

    async def fake_list_demands(
        self: MoySkladClient,
        *,
        offset: int,
        limit: int,
        filters: list[str] | None = None,
    ) -> dict[str, Any]:
        invalid_demand = demand_payload("bad-demand")
        invalid_demand.pop("agent")
        return {
            "meta": {"size": 1, "limit": limit, "offset": offset},
            "rows": [invalid_demand] if offset == 0 else [],
        }

    monkeypatch.setattr(
        MoySkladClient,
        "list_counterparties",
        fake_list_counterparties,
    )
    monkeypatch.setattr(MoySkladClient, "list_demands", fake_list_demands)
    owner = register_company(client)
    integration = create_moysklad_integration(client, token=owner["access_token"])

    sync_run = queue_and_execute_sync(
        client,
        token=owner["access_token"],
        integration_id=integration["id"],
    )
    errors_response = client.get(
        f"/api/v1/sync-runs/{sync_run['id']}/errors",
        headers=auth_headers(owner["access_token"]),
    )

    assert sync_run["status"] == "partially_failed"
    assert sync_run["stats_json"]["skipped_sales"] == 1
    assert errors_response.json()["items"][0]["external_id"] == "bad-demand"
    assert errors_response.json()["items"][0]["error_code"] == "mapping_error"


def test_moysklad_demand_outside_campaign_does_not_affect_progress(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_list_counterparties(
        self: MoySkladClient,
        *,
        offset: int,
        limit: int,
    ) -> dict[str, Any]:
        if offset > 0:
            return {"meta": {"size": 0, "limit": limit, "offset": offset}, "rows": []}
        return {
            "meta": {"size": 1, "limit": limit, "offset": offset},
            "rows": [counterparty_payload()],
        }

    async def fake_list_demands(
        self: MoySkladClient,
        *,
        offset: int,
        limit: int,
        filters: list[str] | None = None,
    ) -> dict[str, Any]:
        if offset > 0:
            return {"meta": {"size": 0, "limit": limit, "offset": offset}, "rows": []}
        return {
            "meta": {"size": 1, "limit": limit, "offset": offset},
            "rows": [demand_payload(moment="2025-06-15 10:30:00")],
        }

    monkeypatch.setattr(
        MoySkladClient,
        "list_counterparties",
        fake_list_counterparties,
    )
    monkeypatch.setattr(MoySkladClient, "list_demands", fake_list_demands)
    owner = register_company(client)
    campaign = create_active_campaign(client, token=owner["access_token"])
    integration = create_moysklad_integration(client, token=owner["access_token"])

    sync_run = queue_and_execute_sync(
        client,
        token=owner["access_token"],
        integration_id=integration["id"],
    )
    customers_response = client.get(
        "/api/v1/customers",
        headers=auth_headers(owner["access_token"]),
    )
    customer = customers_response.json()["items"][0]
    progress_response = client.get(
        f"/api/v1/progress/campaigns/{campaign['id']}/customers/{customer['id']}",
        headers=auth_headers(owner["access_token"]),
    )

    assert sync_run["status"] == "success"
    assert progress_response.status_code == 200
    assert progress_response.json()["total_amount_minor"] == 0


def test_moysklad_missing_credentials_rejected_on_create(
    client: TestClient,
) -> None:
    owner = register_company(client)

    response = client.post(
        "/api/v1/integrations",
        headers=auth_headers(owner["access_token"]),
        json={"provider": "moysklad", "name": "MoySklad"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize(
    ("status_code", "message"),
    [
        (401, "MoySklad authentication failed."),
        (500, "MoySklad service error."),
    ],
)
def test_moysklad_test_and_sync_handle_provider_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    message: str,
) -> None:
    async def fake_list_counterparties(
        self: MoySkladClient,
        *,
        offset: int,
        limit: int,
    ) -> dict[str, Any]:
        raise MoySkladAPIError(
            status_code=status_code,
            message=message,
            details={"status_code": status_code},
        )

    monkeypatch.setattr(
        MoySkladClient,
        "list_counterparties",
        fake_list_counterparties,
    )
    owner = register_company(client)
    integration = create_moysklad_integration(client, token=owner["access_token"])

    test_response = client.post(
        f"/api/v1/integrations/{integration['id']}/test",
        headers=auth_headers(owner["access_token"]),
    )
    sync_run = queue_and_execute_sync(
        client,
        token=owner["access_token"],
        integration_id=integration["id"],
    )

    assert test_response.status_code == 200, test_response.json()
    assert test_response.json()["ok"] is False
    assert "moysklad-secret" not in str(test_response.json())
    assert sync_run["status"] == "failed"
    assert sync_run["error_summary"] == message
    assert "moysklad-secret" not in str(sync_run)
