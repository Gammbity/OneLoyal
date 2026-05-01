from typing import Any

from fastapi.testclient import TestClient


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


def create_campaign(
    client: TestClient,
    *,
    token: str,
    title: str = "Year End Gifts",
    start_date: str = "2026-01-01",
    end_date: str = "2026-12-31",
    currency: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": title,
        "description": "Annual loyalty campaign",
        "start_date": start_date,
        "end_date": end_date,
    }
    if currency is not None:
        payload["currency"] = currency

    response = client.post(
        "/api/v1/campaigns",
        headers=auth_headers(token),
        json=payload,
    )
    assert response.status_code == 201, response.json()
    return response.json()


def create_tier(
    client: TestClient,
    *,
    token: str,
    campaign_id: str,
    title: str = "Powerbank",
    amount: int = 10_000_000,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/campaigns/{campaign_id}/gift-tiers",
        headers=auth_headers(token),
        json={"title": title, "required_amount_minor": amount},
    )
    assert response.status_code == 201, response.json()
    return response.json()


def test_owner_and_admin_can_create_campaign(client: TestClient) -> None:
    owner = register_company(client)
    admin = create_user_and_login(
        client,
        owner_token=owner["access_token"],
        email="admin@example.com",
        role="admin",
    )

    owner_campaign = create_campaign(client, token=owner["access_token"])
    admin_campaign = create_campaign(
        client,
        token=admin["access_token"],
        title="Admin Campaign",
    )

    assert owner_campaign["status"] == "draft"
    assert owner_campaign["currency"] == "UZS"
    assert admin_campaign["title"] == "Admin Campaign"


def test_sales_manager_cannot_create_campaign(client: TestClient) -> None:
    owner = register_company(client)
    sales = create_user_and_login(
        client,
        owner_token=owner["access_token"],
        email="sales@example.com",
        role="sales_manager",
    )

    response = client.post(
        "/api/v1/campaigns",
        headers=auth_headers(sales["access_token"]),
        json={
            "title": "Blocked",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        },
    )

    assert response.status_code == 403


def test_unauthenticated_cannot_access_campaigns(client: TestClient) -> None:
    response = client.get("/api/v1/campaigns")

    assert response.status_code == 401


def test_list_campaigns_is_company_scoped(client: TestClient) -> None:
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
    create_campaign(client, token=company_one["access_token"], title="Company One")
    create_campaign(client, token=company_two["access_token"], title="Company Two")

    response = client.get(
        "/api/v1/campaigns",
        headers=auth_headers(company_one["access_token"]),
    )

    assert response.status_code == 200
    titles = {item["title"] for item in response.json()["items"]}
    assert titles == {"Company One"}


def test_get_campaign_cross_company_returns_404(client: TestClient) -> None:
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
    campaign = create_campaign(client, token=company_one["access_token"])

    response = client.get(
        f"/api/v1/campaigns/{campaign['id']}",
        headers=auth_headers(company_two["access_token"]),
    )

    assert response.status_code == 404


def test_update_campaign_and_invalid_date_range(client: TestClient) -> None:
    owner = register_company(client)
    campaign = create_campaign(client, token=owner["access_token"])

    update_response = client.patch(
        f"/api/v1/campaigns/{campaign['id']}",
        headers=auth_headers(owner["access_token"]),
        json={"title": "Updated Campaign", "allow_claims": False},
    )

    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Updated Campaign"
    assert update_response.json()["allow_claims"] is False

    invalid_response = client.post(
        "/api/v1/campaigns",
        headers=auth_headers(owner["access_token"]),
        json={
            "title": "Invalid",
            "start_date": "2026-12-31",
            "end_date": "2026-01-01",
        },
    )

    assert invalid_response.status_code == 422


def test_campaign_activation_lifecycle(client: TestClient) -> None:
    owner = register_company(client)
    campaign = create_campaign(client, token=owner["access_token"])

    no_tiers_response = client.post(
        f"/api/v1/campaigns/{campaign['id']}/activate",
        headers=auth_headers(owner["access_token"]),
    )
    assert no_tiers_response.status_code == 409

    create_tier(client, token=owner["access_token"], campaign_id=campaign["id"])
    activate_response = client.post(
        f"/api/v1/campaigns/{campaign['id']}/activate",
        headers=auth_headers(owner["access_token"]),
    )
    assert activate_response.status_code == 200
    assert activate_response.json()["status"] == "active"

    pause_response = client.post(
        f"/api/v1/campaigns/{campaign['id']}/pause",
        headers=auth_headers(owner["access_token"]),
    )
    assert pause_response.status_code == 200
    assert pause_response.json()["status"] == "paused"

    reactivate_response = client.post(
        f"/api/v1/campaigns/{campaign['id']}/activate",
        headers=auth_headers(owner["access_token"]),
    )
    assert reactivate_response.status_code == 200

    complete_response = client.post(
        f"/api/v1/campaigns/{campaign['id']}/complete",
        headers=auth_headers(owner["access_token"]),
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "completed"


def test_archived_campaign_cannot_be_activated(client: TestClient) -> None:
    owner = register_company(client)
    campaign = create_campaign(client, token=owner["access_token"])
    archive_response = client.post(
        f"/api/v1/campaigns/{campaign['id']}/archive",
        headers=auth_headers(owner["access_token"]),
    )
    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == "archived"

    activate_response = client.post(
        f"/api/v1/campaigns/{campaign['id']}/activate",
        headers=auth_headers(owner["access_token"]),
    )

    assert activate_response.status_code == 409


def test_create_tier_and_currency_inherits_campaign(client: TestClient) -> None:
    owner = register_company(client)
    campaign = create_campaign(
        client,
        token=owner["access_token"],
        currency="usd",
    )

    tier = create_tier(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
    )

    assert tier["currency"] == "USD"
    assert tier["available_quantity"] is None
    assert tier["stock_tracking_mode"] == "none"


def test_tier_amount_validation_and_duplicate_rejected(client: TestClient) -> None:
    owner = register_company(client)
    campaign = create_campaign(client, token=owner["access_token"])

    invalid_response = client.post(
        f"/api/v1/campaigns/{campaign['id']}/gift-tiers",
        headers=auth_headers(owner["access_token"]),
        json={"title": "Invalid", "required_amount_minor": 0},
    )
    assert invalid_response.status_code == 422

    create_tier(client, token=owner["access_token"], campaign_id=campaign["id"])
    duplicate_response = client.post(
        f"/api/v1/campaigns/{campaign['id']}/gift-tiers",
        headers=auth_headers(owner["access_token"]),
        json={"title": "Duplicate", "required_amount_minor": 10_000_000},
    )
    assert duplicate_response.status_code == 409


def test_list_tiers_is_company_scoped(client: TestClient) -> None:
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
    campaign_one = create_campaign(client, token=company_one["access_token"])
    campaign_two = create_campaign(client, token=company_two["access_token"])
    create_tier(
        client,
        token=company_one["access_token"],
        campaign_id=campaign_one["id"],
        title="Visible",
    )
    create_tier(
        client,
        token=company_two["access_token"],
        campaign_id=campaign_two["id"],
        title="Hidden",
    )

    response = client.get(
        f"/api/v1/campaigns/{campaign_one['id']}/gift-tiers",
        headers=auth_headers(company_one["access_token"]),
    )
    cross_response = client.get(
        f"/api/v1/campaigns/{campaign_two['id']}/gift-tiers",
        headers=auth_headers(company_one["access_token"]),
    )

    assert response.status_code == 200
    assert [tier["title"] for tier in response.json()] == ["Visible"]
    assert cross_response.status_code == 404


def test_update_delete_and_reorder_tiers(client: TestClient) -> None:
    owner = register_company(client)
    campaign = create_campaign(client, token=owner["access_token"])
    first = create_tier(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        title="Powerbank",
        amount=10_000_000,
    )
    second = create_tier(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        title="AirPods",
        amount=30_000_000,
    )

    update_response = client.patch(
        f"/api/v1/campaigns/{campaign['id']}/gift-tiers/{first['id']}",
        headers=auth_headers(owner["access_token"]),
        json={"title": "Powerbank Pro", "stock_tracking_mode": "soft"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Powerbank Pro"
    assert update_response.json()["stock_tracking_mode"] == "soft"

    reorder_response = client.post(
        f"/api/v1/campaigns/{campaign['id']}/gift-tiers/reorder",
        headers=auth_headers(owner["access_token"]),
        json={"tier_ids": [second["id"], first["id"]]},
    )
    assert reorder_response.status_code == 200
    assert [tier["sort_order"] for tier in reorder_response.json()] == [0, 1]

    delete_response = client.delete(
        f"/api/v1/campaigns/{campaign['id']}/gift-tiers/{first['id']}",
        headers=auth_headers(owner["access_token"]),
    )
    assert delete_response.status_code == 204

    list_response = client.get(
        f"/api/v1/campaigns/{campaign['id']}/gift-tiers",
        headers=auth_headers(owner["access_token"]),
    )
    assert [tier["id"] for tier in list_response.json()] == [second["id"]]


def test_sales_manager_can_read_but_cannot_write_tiers(client: TestClient) -> None:
    owner = register_company(client)
    sales = create_user_and_login(
        client,
        owner_token=owner["access_token"],
        email="sales@example.com",
        role="sales_manager",
    )
    campaign = create_campaign(client, token=owner["access_token"])
    create_tier(client, token=owner["access_token"], campaign_id=campaign["id"])

    read_response = client.get(
        f"/api/v1/campaigns/{campaign['id']}/gift-tiers",
        headers=auth_headers(sales["access_token"]),
    )
    write_response = client.post(
        f"/api/v1/campaigns/{campaign['id']}/gift-tiers",
        headers=auth_headers(sales["access_token"]),
        json={"title": "Blocked", "required_amount_minor": 20_000_000},
    )

    assert read_response.status_code == 200
    assert write_response.status_code == 403


def test_company_id_override_is_ignored(client: TestClient) -> None:
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

    response = client.post(
        "/api/v1/campaigns",
        headers=auth_headers(company_one["access_token"]),
        json={
            "company_id": company_two["company"]["id"],
            "title": "Scoped Correctly",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        },
    )

    assert response.status_code == 201
    assert response.json()["company_id"] == company_one["company"]["id"]

