import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.modules.integrations.models import Integration
from app.modules.sync.models import SyncError, SyncRun
from app.modules.users.models import User


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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


def create_user_and_login(
    client: TestClient,
    *,
    owner_token: str,
    email: str,
    role: str,
    full_name: str | None = None,
) -> dict[str, Any]:
    create_response = client.post(
        "/api/v1/users",
        headers=auth_headers(owner_token),
        json={
            "email": email,
            "full_name": full_name or f"{role.title()} User",
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


def create_platform_admin_and_login(client: TestClient) -> dict[str, Any]:
    SessionLocal = client.app.state.test_sessionmaker

    async def create_user() -> None:
        async with SessionLocal() as session:
            session.add(
                User(
                    company_id=None,
                    email="platform@example.com",
                    full_name="Platform Admin",
                    password_hash=hash_password("super-secret-password"),
                    role="platform_admin",
                    status="active",
                )
            )
            await session.commit()

    asyncio.run(create_user())
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "platform@example.com",
            "password": "super-secret-password",
        },
    )
    assert response.status_code == 200, response.json()
    return response.json()


def create_campaign(client: TestClient, *, token: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/campaigns",
        headers=auth_headers(token),
        json={
            "title": "Reporting Campaign",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "currency": "UZS",
            "allow_claims": True,
        },
    )
    assert response.status_code == 201, response.json()
    return response.json()


def create_tier(
    client: TestClient,
    *,
    token: str,
    campaign_id: str,
    title: str,
    amount: int,
    stock_tracking_mode: str = "soft",
    stock_quantity: int | None = 10,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": title,
        "required_amount_minor": amount,
        "stock_tracking_mode": stock_tracking_mode,
    }
    if stock_quantity is not None:
        payload["stock_quantity"] = stock_quantity
    response = client.post(
        f"/api/v1/campaigns/{campaign_id}/gift-tiers",
        headers=auth_headers(token),
        json=payload,
    )
    assert response.status_code == 201, response.json()
    return response.json()


def create_customer(
    client: TestClient,
    *,
    token: str,
    name: str,
) -> dict[str, Any]:
    slug = name.lower().replace(" ", "-")
    response = client.post(
        "/api/v1/customers",
        headers=auth_headers(token),
        json={
            "name": name,
            "phone": f"+99890{len(name):07d}",
            "email": f"{slug}@example.com",
        },
    )
    assert response.status_code == 201, response.json()
    return response.json()


def create_sale_and_recalculate(
    client: TestClient,
    *,
    token: str,
    campaign_id: str,
    customer_id: str,
    amount: int,
) -> dict[str, Any]:
    sale_response = client.post(
        "/api/v1/sale-records",
        headers=auth_headers(token),
        json={
            "customer_id": customer_id,
            "source_type": "manual",
            "source_key": f"sale-{customer_id}",
            "provider": "manual",
            "document_kind": "sale",
            "document_date": "2026-06-01",
            "effective_date": "2026-06-01",
            "gross_amount_minor": amount,
            "amount_sign": 1,
            "currency": "UZS",
            "currency_scale": 0,
            "payment_status": "paid",
            "document_status": "posted",
        },
    )
    assert sale_response.status_code == 201, sale_response.json()
    progress_response = client.post(
        f"/api/v1/progress/campaigns/{campaign_id}/customers/{customer_id}/recalculate",
        headers=auth_headers(token),
    )
    assert progress_response.status_code == 200, progress_response.json()
    return progress_response.json()


def create_claim(
    client: TestClient,
    *,
    token: str,
    campaign_id: str,
    customer_id: str,
    gift_tier_id: str,
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/reward-claims",
        headers=auth_headers(token),
        json={
            "campaign_id": campaign_id,
            "customer_id": customer_id,
            "gift_tier_id": gift_tier_id,
        },
    )
    assert response.status_code == 201, response.json()
    return response.json()


def claim_action(
    client: TestClient,
    *,
    token: str,
    claim_id: str,
    action: str,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/reward-claims/{claim_id}/{action}",
        headers=auth_headers(token),
        json={},
    )
    assert response.status_code == 200, response.json()
    return response.json()


def assign_customer(
    client: TestClient,
    *,
    token: str,
    customer_id: str,
    sales_manager_user_id: str,
) -> None:
    response = client.post(
        f"/api/v1/customers/{customer_id}/assignments",
        headers=auth_headers(token),
        json={"sales_manager_user_id": sales_manager_user_id},
    )
    assert response.status_code == 201, response.json()


def setup_reports_data(client: TestClient) -> dict[str, Any]:
    owner = register_company(client)
    sales = create_user_and_login(
        client,
        owner_token=owner["access_token"],
        email="sales@example.com",
        role="sales_manager",
        full_name="Sally Manager",
    )
    campaign = create_campaign(client, token=owner["access_token"])
    tiers = {
        "tier1": create_tier(
            client,
            token=owner["access_token"],
            campaign_id=campaign["id"],
            title="Bronze Gift",
            amount=1_000,
            stock_quantity=10,
        ),
        "tier2": create_tier(
            client,
            token=owner["access_token"],
            campaign_id=campaign["id"],
            title="Silver Gift",
            amount=3_000,
            stock_quantity=5,
        ),
        "tier3": create_tier(
            client,
            token=owner["access_token"],
            campaign_id=campaign["id"],
            title="Gold Gift",
            amount=5_000,
            stock_tracking_mode="strict",
            stock_quantity=2,
        ),
    }
    activate_response = client.post(
        f"/api/v1/campaigns/{campaign['id']}/activate",
        headers=auth_headers(owner["access_token"]),
    )
    assert activate_response.status_code == 200, activate_response.json()

    amounts = {
        "alice": ("Alice Close", 800),
        "bob": ("Bob Bronze", 2_500),
        "carla": ("Carla Silver", 4_500),
        "dana": ("Dana Gold", 6_000),
        "eve": ("Eve Rejected", 3_500),
        "frank": ("Frank Cancelled", 3_500),
    }
    customers: dict[str, dict[str, Any]] = {}
    for key, (name, amount) in amounts.items():
        customer = create_customer(client, token=owner["access_token"], name=name)
        customers[key] = customer
        create_sale_and_recalculate(
            client,
            token=owner["access_token"],
            campaign_id=campaign["id"],
            customer_id=customer["id"],
            amount=amount,
        )

    claims = {
        "pending": create_claim(
            client,
            token=owner["access_token"],
            campaign_id=campaign["id"],
            customer_id=customers["bob"]["id"],
            gift_tier_id=tiers["tier1"]["id"],
        )
    }
    approved_claim = create_claim(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customers["carla"]["id"],
        gift_tier_id=tiers["tier2"]["id"],
    )
    claims["approved"] = claim_action(
        client,
        token=owner["access_token"],
        claim_id=approved_claim["id"],
        action="approve",
    )
    fulfilled_claim = create_claim(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customers["dana"]["id"],
        gift_tier_id=tiers["tier3"]["id"],
    )
    approved_for_fulfillment = claim_action(
        client,
        token=owner["access_token"],
        claim_id=fulfilled_claim["id"],
        action="approve",
    )
    claims["fulfilled"] = claim_action(
        client,
        token=owner["access_token"],
        claim_id=approved_for_fulfillment["id"],
        action="fulfill",
    )
    rejected_claim = create_claim(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customers["eve"]["id"],
        gift_tier_id=tiers["tier1"]["id"],
    )
    claims["rejected"] = claim_action(
        client,
        token=owner["access_token"],
        claim_id=rejected_claim["id"],
        action="reject",
    )
    cancelled_claim = create_claim(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customers["frank"]["id"],
        gift_tier_id=tiers["tier1"]["id"],
    )
    claims["cancelled"] = claim_action(
        client,
        token=owner["access_token"],
        claim_id=cancelled_claim["id"],
        action="cancel",
    )

    for customer_key in ["alice", "bob", "dana"]:
        assign_customer(
            client,
            token=owner["access_token"],
            customer_id=customers[customer_key]["id"],
            sales_manager_user_id=sales["user"]["id"],
        )

    return {
        "owner": owner,
        "sales": sales,
        "campaign": campaign,
        "tiers": tiers,
        "customers": customers,
        "claims": claims,
    }


def test_report_access_and_company_boundaries(client: TestClient) -> None:
    data = setup_reports_data(client)
    admin = create_user_and_login(
        client,
        owner_token=data["owner"]["access_token"],
        email="admin@example.com",
        role="admin",
    )
    other = register_company(
        client,
        slug="other",
        owner_email="other@example.com",
    )
    platform = create_platform_admin_and_login(client)
    url = f"/api/v1/reports/campaigns/{data['campaign']['id']}/overview"

    owner_response = client.get(
        url,
        headers=auth_headers(data["owner"]["access_token"]),
    )
    admin_response = client.get(url, headers=auth_headers(admin["access_token"]))
    sales_response = client.get(
        url,
        headers=auth_headers(data["sales"]["access_token"]),
    )
    unauthenticated_response = client.get(url)
    cross_company_response = client.get(
        url,
        headers=auth_headers(other["access_token"]),
    )
    platform_response = client.get(url, headers=auth_headers(platform["access_token"]))

    assert owner_response.status_code == 200
    assert admin_response.status_code == 200
    assert sales_response.status_code == 200
    assert sales_response.json()["total_customers_with_progress"] == 3
    assert unauthenticated_response.status_code == 401
    assert cross_company_response.status_code == 404
    assert platform_response.status_code == 403


def test_campaign_overview_totals_and_tier_breakdown(client: TestClient) -> None:
    data = setup_reports_data(client)

    response = client.get(
        f"/api/v1/reports/campaigns/{data['campaign']['id']}/overview",
        headers=auth_headers(data["owner"]["access_token"]),
    )

    assert response.status_code == 200, response.json()
    payload = response.json()
    assert payload["total_customers_with_progress"] == 6
    assert payload["total_purchase_amount_minor"] == 20_800
    assert payload["average_purchase_amount_minor"] == 3_466
    assert payload["customers_reached_any_tier"] == 5
    assert payload["customers_reached_highest_tier"] == 1
    assert payload["total_active_claims"] == 2
    assert payload["total_fulfilled_claims"] == 1

    breakdown = {item["tier_title"]: item for item in payload["gift_tier_breakdown"]}
    assert breakdown["Bronze Gift"]["customers_currently_at_tier"] == 1
    assert breakdown["Bronze Gift"]["claims_count"] == 3
    assert breakdown["Silver Gift"]["customers_currently_at_tier"] == 3
    assert breakdown["Silver Gift"]["claims_count"] == 1
    assert breakdown["Gold Gift"]["customers_currently_at_tier"] == 1
    assert breakdown["Gold Gift"]["fulfilled_count"] == 1


def test_top_customers_sorting_pagination_and_tier_filter(
    client: TestClient,
) -> None:
    data = setup_reports_data(client)
    campaign_id = data["campaign"]["id"]

    first_page = client.get(
        f"/api/v1/reports/campaigns/{campaign_id}/top-customers?limit=2",
        headers=auth_headers(data["owner"]["access_token"]),
    )
    second_item = client.get(
        f"/api/v1/reports/campaigns/{campaign_id}/top-customers?limit=1&offset=1",
        headers=auth_headers(data["owner"]["access_token"]),
    )
    tier_filtered = client.get(
        (
            f"/api/v1/reports/campaigns/{campaign_id}/top-customers"
            f"?tier_id={data['tiers']['tier2']['id']}"
        ),
        headers=auth_headers(data["owner"]["access_token"]),
    )

    assert first_page.status_code == 200, first_page.json()
    assert [item["customer_name"] for item in first_page.json()] == [
        "Dana Gold",
        "Carla Silver",
    ]
    assert first_page.json()[0]["claim_status"] == "fulfilled"
    assert second_item.status_code == 200, second_item.json()
    assert second_item.json()[0]["customer_name"] == "Carla Silver"
    assert tier_filtered.status_code == 200, tier_filtered.json()
    assert {item["customer_name"] for item in tier_filtered.json()} == {
        "Carla Silver",
        "Eve Rejected",
        "Frank Cancelled",
    }


def test_close_to_next_tier_thresholds_and_ordering(client: TestClient) -> None:
    data = setup_reports_data(client)
    campaign_id = data["campaign"]["id"]

    default_response = client.get(
        f"/api/v1/reports/campaigns/{campaign_id}/close-to-next-tier",
        headers=auth_headers(data["owner"]["access_token"]),
    )
    amount_response = client.get(
        (
            f"/api/v1/reports/campaigns/{campaign_id}/close-to-next-tier"
            "?threshold_amount_minor=500"
        ),
        headers=auth_headers(data["owner"]["access_token"]),
    )

    assert default_response.status_code == 200, default_response.json()
    assert [item["customer_name"] for item in default_response.json()] == [
        "Alice Close"
    ]
    assert default_response.json()[0]["progress_percent"] == "80.00"
    assert amount_response.status_code == 200, amount_response.json()
    assert [item["customer_name"] for item in amount_response.json()] == [
        "Alice Close",
        "Bob Bronze",
        "Carla Silver",
    ]
    assert "Dana Gold" not in {
        item["customer_name"] for item in amount_response.json()
    }


def test_gift_liability_counts_stock_and_claims(client: TestClient) -> None:
    data = setup_reports_data(client)

    response = client.get(
        f"/api/v1/reports/campaigns/{data['campaign']['id']}/gift-liability",
        headers=auth_headers(data["owner"]["access_token"]),
    )

    assert response.status_code == 200, response.json()
    payload = response.json()
    assert payload["total_qualified_customers"] == 5
    assert payload["total_claims"] == 5
    assert payload["total_pending_claims"] == 1
    assert payload["total_approved_claims"] == 1
    assert payload["total_fulfilled_claims"] == 1

    tiers = {item["tier_title"]: item for item in payload["tiers"]}
    assert tiers["Bronze Gift"]["customers_qualified_for_tier"] == 5
    assert tiers["Bronze Gift"]["customers_currently_at_tier"] == 1
    assert tiers["Bronze Gift"]["pending_claims"] == 1
    assert tiers["Bronze Gift"]["stock_quantity"] == 10
    assert tiers["Bronze Gift"]["available_quantity"] == 10
    assert tiers["Silver Gift"]["customers_qualified_for_tier"] == 4
    assert tiers["Silver Gift"]["customers_currently_at_tier"] == 3
    assert tiers["Silver Gift"]["approved_claims"] == 1
    assert tiers["Silver Gift"]["reserved_quantity"] == 1
    assert tiers["Silver Gift"]["available_quantity"] == 4
    assert tiers["Gold Gift"]["customers_qualified_for_tier"] == 1
    assert tiers["Gold Gift"]["customers_currently_at_tier"] == 1
    assert tiers["Gold Gift"]["fulfilled_claims"] == 1
    assert tiers["Gold Gift"]["fulfilled_quantity"] == 1
    assert tiers["Gold Gift"]["available_quantity"] == 1


def test_reward_claims_report_summary_and_filters(client: TestClient) -> None:
    data = setup_reports_data(client)
    base_url = (
        "/api/v1/reports/reward-claims"
        f"?campaign_id={data['campaign']['id']}"
        "&date_from=2000-01-01&date_to=2100-01-01"
    )

    all_claims = client.get(
        base_url,
        headers=auth_headers(data["owner"]["access_token"]),
    )
    fulfilled = client.get(
        f"{base_url}&status=fulfilled",
        headers=auth_headers(data["owner"]["access_token"]),
    )
    invalid_range = client.get(
        (
            "/api/v1/reports/reward-claims"
            "?date_from=2026-12-31&date_to=2026-01-01"
        ),
        headers=auth_headers(data["owner"]["access_token"]),
    )

    assert all_claims.status_code == 200, all_claims.json()
    assert all_claims.json()["summary"] == {
        "total": 5,
        "pending": 1,
        "approved": 1,
        "rejected": 1,
        "fulfilled": 1,
        "cancelled": 1,
    }
    assert fulfilled.status_code == 200, fulfilled.json()
    assert fulfilled.json()["summary"]["total"] == 1
    assert fulfilled.json()["items"][0]["status"] == "fulfilled"
    assert fulfilled.json()["items"][0]["customer_name"] == "Dana Gold"
    assert invalid_range.status_code == 422


def create_fake_integration(client: TestClient, *, token: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/integrations",
        headers=auth_headers(token),
        json={
            "provider": "fake",
            "name": "Fake ERP",
            "settings_json": {"customers": [], "sales": []},
        },
    )
    assert response.status_code == 201, response.json()
    return response.json()


def insert_sync_health_rows(
    client: TestClient,
    *,
    company_id: str,
    integration_id: str,
) -> None:
    SessionLocal = client.app.state.test_sessionmaker
    base = datetime(2026, 5, 1, 10, 0, tzinfo=UTC)

    async def insert_rows() -> None:
        async with SessionLocal() as session:
            integration = await session.get(Integration, UUID(integration_id))
            integration.status = "active"
            integration.last_attempted_sync_at = base + timedelta(hours=2)
            integration.last_successful_sync_at = base + timedelta(minutes=5)
            integration.next_sync_at = base + timedelta(days=1)
            success = SyncRun(
                company_id=UUID(company_id),
                integration_id=UUID(integration_id),
                sync_type="manual",
                status="success",
                started_at=base,
                finished_at=base + timedelta(minutes=5),
                cursor_before_json={},
                cursor_after_json={},
                stats_json={"created_customers": 1},
            )
            failed = SyncRun(
                company_id=UUID(company_id),
                integration_id=UUID(integration_id),
                sync_type="scheduled",
                status="failed",
                started_at=base + timedelta(hours=1),
                finished_at=base + timedelta(hours=1, minutes=1),
                cursor_before_json={},
                cursor_after_json={},
                stats_json={"failed_records": 1},
                error_summary="Connection failed",
            )
            partial = SyncRun(
                company_id=UUID(company_id),
                integration_id=UUID(integration_id),
                sync_type="manual",
                status="partially_failed",
                started_at=base + timedelta(hours=2),
                finished_at=base + timedelta(hours=2, minutes=1),
                cursor_before_json={},
                cursor_after_json={},
                stats_json={"failed_records": 1, "created_sales": 1},
                error_summary="Some rows failed",
            )
            session.add_all([success, failed, partial])
            await session.flush()
            session.add(
                SyncError(
                    company_id=UUID(company_id),
                    sync_run_id=partial.id,
                    entity_type="sale_record",
                    external_id="sale-1",
                    severity="error",
                    error_code="validation_error",
                    message="Amount is invalid",
                    raw_payload_json={"secret": "hidden"},
                )
            )
            await session.commit()

    asyncio.run(insert_rows())


def test_sync_health_report_counts_errors_and_integration_filter(
    client: TestClient,
) -> None:
    owner = register_company(client)
    integration = create_fake_integration(client, token=owner["access_token"])
    insert_sync_health_rows(
        client,
        company_id=owner["company"]["id"],
        integration_id=integration["id"],
    )

    response = client.get(
        "/api/v1/reports/sync-health?date_from=2026-05-01&date_to=2026-05-31",
        headers=auth_headers(owner["access_token"]),
    )
    filtered = client.get(
        f"/api/v1/reports/sync-health?integration_id={integration['id']}&limit=2",
        headers=auth_headers(owner["access_token"]),
    )

    assert response.status_code == 200, response.json()
    payload = response.json()
    assert payload["summary"] == {
        "total_integrations": 1,
        "active_integrations": 1,
        "failed_runs": 1,
        "partially_failed_runs": 1,
        "successful_runs": 1,
    }
    assert payload["integrations"][0]["recent_success_count"] == 1
    assert payload["integrations"][0]["recent_failed_count"] == 1
    assert payload["integrations"][0]["recent_partially_failed_count"] == 1
    assert payload["integrations"][0]["last_error_summary"] == "Some rows failed"
    assert payload["recent_runs"][0]["status"] == "partially_failed"
    assert "raw_payload_json" not in str(payload)

    assert filtered.status_code == 200, filtered.json()
    assert len(filtered.json()["recent_runs"]) == 2
    assert filtered.json()["integrations"][0]["integration_id"] == integration["id"]


def test_sales_manager_performance_foundation(client: TestClient) -> None:
    data = setup_reports_data(client)

    owner_response = client.get(
        f"/api/v1/reports/sales-managers?campaign_id={data['campaign']['id']}",
        headers=auth_headers(data["owner"]["access_token"]),
    )
    sales_response = client.get(
        f"/api/v1/reports/sales-managers?campaign_id={data['campaign']['id']}",
        headers=auth_headers(data["sales"]["access_token"]),
    )

    assert owner_response.status_code == 200, owner_response.json()
    assert sales_response.status_code == 200, sales_response.json()
    owner_items = owner_response.json()
    sales_items = sales_response.json()
    assert len(owner_items) == 1
    assert len(sales_items) == 1
    item = owner_items[0]
    assert item["user_id"] == data["sales"]["user"]["id"]
    assert item["assigned_customer_count"] == 3
    assert item["total_purchase_amount_minor"] == 9_300
    assert item["customers_reached_any_tier"] == 2
    assert item["customers_close_to_next_tier_count"] == 1
    assert item["fulfilled_claims_count"] == 1
