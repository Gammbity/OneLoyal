import asyncio
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.common.datetime import utc_now
from app.modules.integrations.models import IntegrationCredential
from app.modules.sync.models import SyncRun


def register_company(
    client: TestClient,
    *,
    slug: str = "acme",
    owner_email: str = "owner@example.com",
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


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_login(
    client: TestClient,
    *,
    owner_token: str,
    email: str,
    role: str,
) -> dict[str, Any]:
    create_response = client.post(
        "/api/v1/users",
        headers=auth_headers(owner_token),
        json={
            "email": email,
            "full_name": f"{role.title()} User",
            "password": "super-secret-password",
            "role": role,
        },
    )
    assert create_response.status_code == 201, create_response.json()
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "super-secret-password"},
    )
    assert login_response.status_code == 200, login_response.json()
    return login_response.json()


def fake_settings(
    *,
    gross_amount_minor: int = 30_000_000,
    customer_external_id: str = "cust_1",
    sale_external_id: str = "sale_1",
) -> dict[str, Any]:
    return {
        "customers": [
            {
                "external_id": "cust_1",
                "name": "ERP Customer",
                "phone": "+998901234567",
                "email": "erp-customer@example.com",
                "tax_id": "TIN-1",
            }
        ],
        "sales": [
            {
                "external_id": sale_external_id,
                "customer_external_id": customer_external_id,
                "document_kind": "sale",
                "document_date": "2026-06-15",
                "effective_date": "2026-06-15",
                "gross_amount_minor": gross_amount_minor,
                "currency": "UZS",
                "payment_status": "paid",
                "document_status": "posted",
                "external_document_number": "INV-1",
            }
        ],
    }


def create_fake_integration(
    client: TestClient,
    *,
    token: str,
    settings_json: dict[str, Any] | None = None,
    credentials_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "provider": "fake",
        "name": "Fake ERP",
        "settings_json": settings_json or fake_settings(),
    }
    if credentials_json is not None:
        payload["credentials_json"] = credentials_json
    response = client.post(
        "/api/v1/integrations",
        headers=auth_headers(token),
        json=payload,
    )
    assert response.status_code == 201, response.json()
    return response.json()


def sync_integration(
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
    return response.json()


def create_active_campaign(
    client: TestClient,
    *,
    token: str,
) -> dict[str, Any]:
    campaign_response = client.post(
        "/api/v1/campaigns",
        headers=auth_headers(token),
        json={
            "title": "Active Sync Campaign",
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


def test_integration_api_rbac_credentials_and_scoping(client: TestClient) -> None:
    company_one = register_company(
        client,
        slug="company-one",
        owner_email="one@example.com",
    )
    company_two = register_company(
        client,
        slug="company-two",
        owner_email="two@example.com",
    )
    sales = create_user_and_login(
        client,
        owner_token=company_one["access_token"],
        email="sales@example.com",
        role="sales_manager",
    )

    integration = create_fake_integration(
        client,
        token=company_one["access_token"],
        credentials_json={"api_key": "fake-secret"},
    )
    sales_create = client.post(
        "/api/v1/integrations",
        headers=auth_headers(sales["access_token"]),
        json={"provider": "fake", "name": "Blocked"},
    )
    list_response = client.get(
        "/api/v1/integrations",
        headers=auth_headers(company_one["access_token"]),
    )
    cross_get = client.get(
        f"/api/v1/integrations/{integration['id']}",
        headers=auth_headers(company_two["access_token"]),
    )
    unsupported = client.post(
        "/api/v1/integrations",
        headers=auth_headers(company_one["access_token"]),
        json={"provider": "moysklad", "name": "MoySklad"},
    )

    assert integration["has_active_credentials"] is True
    assert "credentials_json" not in integration
    assert "encrypted_credentials" not in integration
    assert sales_create.status_code == 403
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [integration["id"]]
    assert cross_get.status_code == 404
    assert unsupported.status_code == 422


def test_credentials_are_encrypted_at_rest(client: TestClient) -> None:
    owner = register_company(client)
    integration = create_fake_integration(
        client,
        token=owner["access_token"],
        credentials_json={"api_key": "plain-secret"},
    )
    SessionLocal = client.app.state.test_sessionmaker

    async def load_encrypted_credentials() -> str:
        async with SessionLocal() as session:
            result = await session.execute(
                select(IntegrationCredential).where(
                    IntegrationCredential.integration_id == UUID(integration["id"])
                )
            )
            credential = result.scalar_one()
            return credential.encrypted_credentials

    encrypted_credentials = asyncio.run(load_encrypted_credentials())

    assert encrypted_credentials
    assert "plain-secret" not in encrypted_credentials
    assert encrypted_credentials != '{"api_key": "plain-secret"}'


def test_update_and_test_fake_integration(client: TestClient) -> None:
    owner = register_company(client)
    integration = create_fake_integration(client, token=owner["access_token"])

    update_response = client.patch(
        f"/api/v1/integrations/{integration['id']}",
        headers=auth_headers(owner["access_token"]),
        json={
            "name": "Updated Fake",
            "settings_json": fake_settings(gross_amount_minor=5),
        },
    )
    test_response = client.post(
        f"/api/v1/integrations/{integration['id']}/test",
        headers=auth_headers(owner["access_token"]),
    )

    assert update_response.status_code == 200, update_response.json()
    assert update_response.json()["name"] == "Updated Fake"
    assert test_response.status_code == 200
    assert test_response.json()["ok"] is True


def test_manual_sync_creates_customers_refs_sales_and_progress(
    client: TestClient,
) -> None:
    owner = register_company(client)
    campaign = create_active_campaign(client, token=owner["access_token"])
    integration = create_fake_integration(client, token=owner["access_token"])

    sync_run = sync_integration(
        client,
        token=owner["access_token"],
        integration_id=integration["id"],
    )
    customers_response = client.get(
        "/api/v1/customers?search=ERP Customer",
        headers=auth_headers(owner["access_token"]),
    )
    customer = customers_response.json()["items"][0]
    refs_response = client.get(
        f"/api/v1/customers/{customer['id']}/external-refs",
        headers=auth_headers(owner["access_token"]),
    )
    sales_response = client.get(
        f"/api/v1/sale-records?customer_id={customer['id']}",
        headers=auth_headers(owner["access_token"]),
    )
    progress_response = client.get(
        f"/api/v1/progress/campaigns/{campaign['id']}/customers/{customer['id']}",
        headers=auth_headers(owner["access_token"]),
    )
    integration_response = client.get(
        f"/api/v1/integrations/{integration['id']}",
        headers=auth_headers(owner["access_token"]),
    )

    assert sync_run["status"] == "success"
    assert sync_run["stats_json"]["created_customers"] == 1
    assert sync_run["stats_json"]["created_sales"] == 1
    assert sync_run["stats_json"]["recalculated_progress_count"] == 1
    assert customer["name"] == "ERP Customer"
    assert refs_response.json()[0]["provider"] == "fake"
    assert refs_response.json()[0]["external_id"] == "cust_1"
    assert sales_response.json()["items"][0]["source_key"] == "fake:sale_1"
    assert sales_response.json()["items"][0]["gross_amount_minor"] == 30_000_000
    assert progress_response.status_code == 200
    assert progress_response.json()["total_amount_minor"] == 30_000_000
    assert integration_response.json()["last_attempted_sync_at"] is not None
    assert integration_response.json()["last_successful_sync_at"] is not None


def test_sync_is_idempotent_and_changed_sale_updates_existing_record(
    client: TestClient,
) -> None:
    owner = register_company(client)
    integration = create_fake_integration(
        client,
        token=owner["access_token"],
        settings_json=fake_settings(gross_amount_minor=10_000_000),
    )
    first_sync = sync_integration(
        client,
        token=owner["access_token"],
        integration_id=integration["id"],
    )
    second_sync = sync_integration(
        client,
        token=owner["access_token"],
        integration_id=integration["id"],
    )
    patch_response = client.patch(
        f"/api/v1/integrations/{integration['id']}",
        headers=auth_headers(owner["access_token"]),
        json={"settings_json": fake_settings(gross_amount_minor=20_000_000)},
    )
    assert patch_response.status_code == 200, patch_response.json()
    third_sync = sync_integration(
        client,
        token=owner["access_token"],
        integration_id=integration["id"],
    )
    customers_response = client.get(
        "/api/v1/customers",
        headers=auth_headers(owner["access_token"]),
    )
    sales_response = client.get(
        "/api/v1/sale-records",
        headers=auth_headers(owner["access_token"]),
    )

    assert first_sync["stats_json"]["created_sales"] == 1
    assert second_sync["stats_json"]["created_customers"] == 0
    assert second_sync["stats_json"]["created_sales"] == 0
    assert third_sync["stats_json"]["updated_sales"] == 1
    assert customers_response.json()["pagination"]["total"] == 1
    assert sales_response.json()["pagination"]["total"] == 1
    assert sales_response.json()["items"][0]["gross_amount_minor"] == 20_000_000


def test_missing_sale_customer_creates_sync_error_and_partial_failure(
    client: TestClient,
) -> None:
    owner = register_company(client)
    integration = create_fake_integration(
        client,
        token=owner["access_token"],
        settings_json=fake_settings(customer_external_id="missing_customer"),
    )

    sync_run = sync_integration(
        client,
        token=owner["access_token"],
        integration_id=integration["id"],
    )
    errors_response = client.get(
        f"/api/v1/sync-runs/{sync_run['id']}/errors",
        headers=auth_headers(owner["access_token"]),
    )
    integration_response = client.get(
        f"/api/v1/integrations/{integration['id']}",
        headers=auth_headers(owner["access_token"]),
    )

    assert sync_run["status"] == "partially_failed"
    assert sync_run["stats_json"]["skipped_sales"] == 1
    assert sync_run["stats_json"]["failed_records"] == 1
    assert errors_response.status_code == 200
    errors = errors_response.json()["items"]
    assert len(errors) == 1
    assert errors[0]["entity_type"] == "sale_record"
    assert errors[0]["external_id"] == "sale_1"
    assert integration_response.json()["last_attempted_sync_at"] is not None
    assert integration_response.json()["last_successful_sync_at"] is None


def test_failed_provider_connection_marks_sync_failed(client: TestClient) -> None:
    owner = register_company(client)
    integration = create_fake_integration(
        client,
        token=owner["access_token"],
        settings_json={"fail_connection": True},
    )

    sync_run = sync_integration(
        client,
        token=owner["access_token"],
        integration_id=integration["id"],
    )
    integration_response = client.get(
        f"/api/v1/integrations/{integration['id']}",
        headers=auth_headers(owner["access_token"]),
    )

    assert sync_run["status"] == "failed"
    assert sync_run["error_summary"]
    assert integration_response.json()["last_attempted_sync_at"] is not None
    assert integration_response.json()["last_successful_sync_at"] is None
    assert integration_response.json()["status"] == "error"


def test_running_sync_conflict_is_rejected(client: TestClient) -> None:
    owner = register_company(client)
    integration = create_fake_integration(client, token=owner["access_token"])
    SessionLocal = client.app.state.test_sessionmaker

    async def insert_running_sync() -> None:
        async with SessionLocal() as session:
            session.add(
                SyncRun(
                    company_id=UUID(owner["company"]["id"]),
                    integration_id=UUID(integration["id"]),
                    sync_type="manual",
                    status="running",
                    started_at=utc_now(),
                    cursor_before_json={},
                    cursor_after_json={},
                    stats_json={},
                )
            )
            await session.commit()

    asyncio.run(insert_running_sync())

    response = client.post(
        f"/api/v1/integrations/{integration['id']}/sync",
        headers=auth_headers(owner["access_token"]),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_sync_run_api_is_company_scoped(client: TestClient) -> None:
    company_one = register_company(
        client,
        slug="company-one",
        owner_email="one@example.com",
    )
    company_two = register_company(
        client,
        slug="company-two",
        owner_email="two@example.com",
    )
    integration = create_fake_integration(
        client,
        token=company_one["access_token"],
        settings_json=fake_settings(customer_external_id="missing_customer"),
    )
    sync_run = sync_integration(
        client,
        token=company_one["access_token"],
        integration_id=integration["id"],
    )

    list_response = client.get(
        "/api/v1/sync-runs",
        headers=auth_headers(company_one["access_token"]),
    )
    get_response = client.get(
        f"/api/v1/sync-runs/{sync_run['id']}",
        headers=auth_headers(company_one["access_token"]),
    )
    errors_response = client.get(
        f"/api/v1/sync-runs/{sync_run['id']}/errors",
        headers=auth_headers(company_one["access_token"]),
    )
    cross_get = client.get(
        f"/api/v1/sync-runs/{sync_run['id']}",
        headers=auth_headers(company_two["access_token"]),
    )

    assert list_response.status_code == 200
    assert list_response.json()["pagination"]["total"] == 1
    assert get_response.status_code == 200
    assert errors_response.status_code == 200
    assert errors_response.json()["pagination"]["total"] == 1
    assert cross_get.status_code == 404
