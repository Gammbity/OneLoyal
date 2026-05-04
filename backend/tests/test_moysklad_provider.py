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
from app.modules.integrations.providers.moysklad.provider import MoySkladProvider
from app.modules.integrations.providers.registry import provider_registry


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


def dummy_integration() -> Integration:
    return Integration(
        id=uuid4(),
        company_id=uuid4(),
        provider="moysklad",
        name="MoySklad",
        settings_json={},
        sync_cursor_json={},
    )


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

    monkeypatch.setattr(
        MoySkladClient,
        "list_counterparties",
        fake_list_counterparties,
    )
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
    sync_response = client.post(
        f"/api/v1/integrations/{integration['id']}/sync",
        headers=auth_headers(owner["access_token"]),
    )
    second_sync_response = client.post(
        f"/api/v1/integrations/{integration['id']}/sync",
        headers=auth_headers(owner["access_token"]),
    )
    customers_response = client.get(
        "/api/v1/customers",
        headers=auth_headers(owner["access_token"]),
    )

    assert test_response.status_code == 200, test_response.json()
    assert test_response.json()["ok"] is True
    assert sync_response.status_code == 200, sync_response.json()
    sync_run = sync_response.json()
    assert sync_run["status"] == "success"
    assert sync_run["stats_json"]["fetched_customers"] == 2
    assert sync_run["stats_json"]["created_customers"] == 2
    assert sync_run["stats_json"]["fetched_sales"] == 0
    assert sync_run["stats_json"]["sales_not_supported"] is True
    assert sync_run["stats_json"]["recalculated_progress_count"] == 0
    assert second_sync_response.status_code == 200, second_sync_response.json()
    assert second_sync_response.json()["stats_json"]["created_customers"] == 0
    assert second_sync_response.json()["stats_json"]["updated_customers"] == 0
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

    monkeypatch.setattr(
        MoySkladClient,
        "list_counterparties",
        fake_list_counterparties,
    )
    owner = register_company(client)
    integration = create_moysklad_integration(client, token=owner["access_token"])
    SessionLocal = client.app.state.test_sessionmaker

    sync_response = client.post(
        f"/api/v1/integrations/{integration['id']}/sync",
        headers=auth_headers(owner["access_token"]),
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

    assert sync_response.status_code == 200, sync_response.json()
    assert integration["has_active_credentials"] is True
    assert "credentials_json" not in integration
    assert "encrypted_credentials" not in integration
    assert "moysklad-secret" not in encrypted_credentials
    assert customer.name == "MoySklad Customer"
    assert external_ref.provider == "moysklad"
    assert external_ref.external_id == "counterparty-1"


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


def test_moysklad_test_and_sync_handle_auth_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_list_counterparties(
        self: MoySkladClient,
        *,
        offset: int,
        limit: int,
    ) -> dict[str, Any]:
        raise MoySkladAPIError(
            status_code=401,
            message="MoySklad authentication failed.",
            details={"status_code": 401},
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
    sync_response = client.post(
        f"/api/v1/integrations/{integration['id']}/sync",
        headers=auth_headers(owner["access_token"]),
    )

    assert test_response.status_code == 200, test_response.json()
    assert test_response.json()["ok"] is False
    assert "moysklad-secret" not in str(test_response.json())
    assert sync_response.status_code == 200, sync_response.json()
    sync_run = sync_response.json()
    assert sync_run["status"] == "failed"
    assert sync_run["error_summary"] == "MoySklad authentication failed."
    assert "moysklad-secret" not in str(sync_run)
