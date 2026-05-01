from datetime import datetime, timedelta
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
    payload = login_response.json()
    payload["created_user"] = create_response.json()
    return payload


def create_customer(
    client: TestClient,
    *,
    token: str,
    name: str = "Customer One",
    email: str = "customer@example.com",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/customers",
        headers=auth_headers(token),
        json={"name": name, "email": email},
    )
    assert response.status_code == 201, response.json()
    return response.json()


def create_campaign(
    client: TestClient,
    *,
    token: str,
    title: str = "Active Rewards",
    start_date: str = "2026-01-01",
    end_date: str = "2026-12-31",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/campaigns",
        headers=auth_headers(token),
        json={
            "title": title,
            "start_date": start_date,
            "end_date": end_date,
            "currency": "UZS",
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
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/campaigns/{campaign_id}/gift-tiers",
        headers=auth_headers(token),
        json={"title": title, "required_amount_minor": amount},
    )
    assert response.status_code == 201, response.json()
    return response.json()


def activate_campaign(
    client: TestClient,
    *,
    token: str,
    campaign_id: str,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/campaigns/{campaign_id}/activate",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.json()
    return response.json()


def create_active_campaign_with_tiers(
    client: TestClient,
    *,
    token: str,
    title: str = "Active Rewards",
    start_date: str = "2026-01-01",
    end_date: str = "2026-12-31",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    campaign = create_campaign(
        client,
        token=token,
        title=title,
        start_date=start_date,
        end_date=end_date,
    )
    tiers = [
        create_tier(
            client,
            token=token,
            campaign_id=campaign["id"],
            title="Powerbank",
            amount=10_000_000,
        ),
        create_tier(
            client,
            token=token,
            campaign_id=campaign["id"],
            title="AirPods",
            amount=30_000_000,
        ),
    ]
    campaign = activate_campaign(client, token=token, campaign_id=campaign["id"])
    return campaign, tiers


def create_sale(
    client: TestClient,
    *,
    token: str,
    customer_id: str,
    source_key: str,
    amount: int,
    effective_date: str = "2026-06-01",
    external_document_number: str | None = None,
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/sale-records",
        headers=auth_headers(token),
        json={
            "customer_id": customer_id,
            "source_type": "manual",
            "source_key": source_key,
            "provider": "manual",
            "document_kind": "sale",
            "external_document_number": external_document_number,
            "document_date": effective_date,
            "effective_date": effective_date,
            "gross_amount_minor": amount,
            "amount_sign": 1,
            "currency": "UZS",
            "currency_scale": 0,
            "payment_status": "paid",
            "document_status": "posted",
            "raw_payload_json": {"secret": "not-for-portal"},
        },
    )
    assert response.status_code == 201, response.json()
    return response.json()


def recalculate_customer(
    client: TestClient,
    *,
    token: str,
    campaign_id: str,
    customer_id: str,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/progress/campaigns/{campaign_id}/customers/{customer_id}"
        "/recalculate",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.json()
    return response.json()


def create_magic_link(
    client: TestClient,
    *,
    token: str,
    customer_id: str,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/customers/{customer_id}/magic-links",
        headers=auth_headers(token),
    )
    assert response.status_code == 201, response.json()
    return response.json()


def create_portal_session(client: TestClient, *, raw_token: str) -> dict[str, Any]:
    response = client.post("/api/v1/portal/session", json={"token": raw_token})
    assert response.status_code == 200, response.json()
    return response.json()


def test_admin_and_sales_manager_can_generate_magic_links(
    client: TestClient,
) -> None:
    owner = register_company(client)
    sales = create_user_and_login(
        client,
        owner_token=owner["access_token"],
        email="sales@example.com",
        role="sales_manager",
    )
    customer = create_customer(client, token=owner["access_token"])

    owner_link = create_magic_link(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
    )
    sales_link = create_magic_link(
        client,
        token=sales["access_token"],
        customer_id=customer["id"],
    )
    unauthenticated = client.post(f"/api/v1/customers/{customer['id']}/magic-links")

    assert owner_link["raw_token"]
    assert owner_link["token_id"]
    assert "token_hash" not in owner_link
    assert sales_link["raw_token"]
    assert unauthenticated.status_code == 401


def test_magic_links_are_company_scoped_and_list_hides_secrets(
    client: TestClient,
) -> None:
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
    customer = create_customer(client, token=company_one["access_token"])
    create_magic_link(
        client,
        token=company_one["access_token"],
        customer_id=customer["id"],
    )

    list_response = client.get(
        f"/api/v1/customers/{customer['id']}/magic-links",
        headers=auth_headers(company_one["access_token"]),
    )
    cross_company = client.post(
        f"/api/v1/customers/{customer['id']}/magic-links",
        headers=auth_headers(company_two["access_token"]),
    )

    assert list_response.status_code == 200
    listed = list_response.json()
    assert len(listed) == 1
    assert "raw_token" not in listed[0]
    assert "token_hash" not in listed[0]
    assert cross_company.status_code == 404


def test_valid_magic_token_creates_reusable_portal_session(
    client: TestClient,
) -> None:
    owner = register_company(client)
    customer = create_customer(client, token=owner["access_token"])
    magic_link = create_magic_link(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
    )

    first_session = create_portal_session(client, raw_token=magic_link["raw_token"])
    second_session = create_portal_session(client, raw_token=magic_link["raw_token"])
    list_response = client.get(
        f"/api/v1/customers/{customer['id']}/magic-links",
        headers=auth_headers(owner["access_token"]),
    )

    assert first_session["portal_access_token"]
    assert first_session["customer"]["id"] == customer["id"]
    assert second_session["portal_access_token"]
    listed = list_response.json()[0]
    assert listed["use_count"] == 2
    assert listed["used_at"] is not None
    assert listed["last_used_at"] is not None


def test_invalid_expired_and_revoked_magic_tokens_are_rejected(
    client: TestClient,
    monkeypatch,
) -> None:
    owner = register_company(client)
    customer = create_customer(client, token=owner["access_token"])
    invalid_response = client.post(
        "/api/v1/portal/session",
        json={"token": "invalid-token-with-enough-length"},
    )
    assert invalid_response.status_code == 401
    assert invalid_response.json()["error"]["request_id"]

    expired_link = create_magic_link(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
    )
    expires_at = datetime.fromisoformat(expired_link["expires_at"])
    monkeypatch.setattr(
        "app.modules.portal.service.utc_now",
        lambda: expires_at + timedelta(seconds=1),
    )
    expired_response = client.post(
        "/api/v1/portal/session",
        json={"token": expired_link["raw_token"]},
    )
    assert expired_response.status_code == 401

    monkeypatch.undo()
    revoked_link = create_magic_link(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
    )
    revoke_response = client.post(
        f"/api/v1/customers/{customer['id']}/magic-links/"
        f"{revoked_link['token_id']}/revoke",
        headers=auth_headers(owner["access_token"]),
    )
    session_response = client.post(
        "/api/v1/portal/session",
        json={"token": revoked_link["raw_token"]},
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json()["revoked_at"] is not None
    assert session_response.status_code == 401


def test_portal_and_admin_auth_tokens_are_not_interchangeable(
    client: TestClient,
) -> None:
    owner = register_company(client)
    customer = create_customer(client, token=owner["access_token"])
    magic_link = create_magic_link(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
    )
    portal_session = create_portal_session(
        client,
        raw_token=magic_link["raw_token"],
    )

    admin_on_portal = client.get(
        "/api/v1/portal/me",
        headers=auth_headers(owner["access_token"]),
    )
    portal_on_admin = client.get(
        "/api/v1/customers",
        headers=auth_headers(portal_session["portal_access_token"]),
    )

    assert admin_on_portal.status_code == 401
    assert portal_on_admin.status_code == 401


def test_portal_me_and_campaign_listing_use_customer_context(
    client: TestClient,
) -> None:
    owner = register_company(client)
    customer = create_customer(client, token=owner["access_token"])
    active_campaign, _ = create_active_campaign_with_tiers(
        client,
        token=owner["access_token"],
    )
    draft_campaign = create_campaign(
        client,
        token=owner["access_token"],
        title="Draft Hidden",
    )
    future_campaign, _ = create_active_campaign_with_tiers(
        client,
        token=owner["access_token"],
        title="Future Hidden",
        start_date="2027-01-01",
        end_date="2027-12-31",
    )
    magic_link = create_magic_link(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
    )
    portal_token = create_portal_session(
        client,
        raw_token=magic_link["raw_token"],
    )["portal_access_token"]

    me_response = client.get("/api/v1/portal/me", headers=auth_headers(portal_token))
    campaigns_response = client.get(
        "/api/v1/portal/campaigns",
        headers=auth_headers(portal_token),
    )

    assert me_response.status_code == 200
    assert me_response.json()["customer"]["id"] == customer["id"]
    assert campaigns_response.status_code == 200
    campaign_ids = {campaign["id"] for campaign in campaigns_response.json()}
    assert active_campaign["id"] in campaign_ids
    assert draft_campaign["id"] not in campaign_ids
    assert future_campaign["id"] not in campaign_ids


def test_portal_progress_returns_snapshot_or_safe_zero_response(
    client: TestClient,
) -> None:
    owner = register_company(client)
    customer = create_customer(client, token=owner["access_token"])
    other_customer = create_customer(
        client,
        token=owner["access_token"],
        name="Other Customer",
        email="other@example.com",
    )
    campaign, tiers = create_active_campaign_with_tiers(
        client,
        token=owner["access_token"],
    )
    create_sale(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        source_key="portal-sale",
        amount=35_000_000,
    )
    recalculate_customer(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
    )

    magic_link = create_magic_link(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
    )
    portal_token = create_portal_session(
        client,
        raw_token=magic_link["raw_token"],
    )["portal_access_token"]
    snapshot_response = client.get(
        f"/api/v1/portal/campaigns/{campaign['id']}/progress",
        headers=auth_headers(portal_token),
    )

    other_magic_link = create_magic_link(
        client,
        token=owner["access_token"],
        customer_id=other_customer["id"],
    )
    other_portal_token = create_portal_session(
        client,
        raw_token=other_magic_link["raw_token"],
    )["portal_access_token"]
    zero_response = client.get(
        f"/api/v1/portal/campaigns/{campaign['id']}/progress",
        headers=auth_headers(other_portal_token),
    )

    assert snapshot_response.status_code == 200
    snapshot = snapshot_response.json()
    assert snapshot["customer"]["id"] == customer["id"]
    assert snapshot["progress"]["is_snapshot_available"] is True
    assert snapshot["progress"]["total_amount_minor"] == 35_000_000
    assert snapshot["progress"]["current_tier_id"] == tiers[1]["id"]
    assert [tier["id"] for tier in snapshot["gift_tiers"]] == [
        tiers[0]["id"],
        tiers[1]["id"],
    ]

    assert zero_response.status_code == 200
    zero = zero_response.json()
    assert zero["customer"]["id"] == other_customer["id"]
    assert zero["progress"]["is_snapshot_available"] is False
    assert zero["progress"]["total_amount_minor"] == 0
    assert zero["progress"]["next_tier_id"] == tiers[0]["id"]
    assert zero["progress"]["amount_left_minor"] == 10_000_000


def test_portal_purchase_history_is_scoped_and_safe(client: TestClient) -> None:
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
    customer = create_customer(client, token=company_one["access_token"])
    other_customer = create_customer(
        client,
        token=company_one["access_token"],
        name="Other Customer",
        email="other@example.com",
    )
    campaign, _ = create_active_campaign_with_tiers(
        client,
        token=company_one["access_token"],
    )
    other_campaign, _ = create_active_campaign_with_tiers(
        client,
        token=company_two["access_token"],
    )
    create_sale(
        client,
        token=company_one["access_token"],
        customer_id=customer["id"],
        source_key="inside",
        amount=10_000_000,
        external_document_number="INV-1",
    )
    create_sale(
        client,
        token=company_one["access_token"],
        customer_id=customer["id"],
        source_key="outside",
        amount=99_000_000,
        effective_date="2027-01-01",
        external_document_number="INV-OUT",
    )
    create_sale(
        client,
        token=company_one["access_token"],
        customer_id=other_customer["id"],
        source_key="other-customer",
        amount=88_000_000,
        external_document_number="INV-OTHER",
    )
    magic_link = create_magic_link(
        client,
        token=company_one["access_token"],
        customer_id=customer["id"],
    )
    portal_token = create_portal_session(
        client,
        raw_token=magic_link["raw_token"],
    )["portal_access_token"]

    history_response = client.get(
        f"/api/v1/portal/campaigns/{campaign['id']}/purchase-history",
        headers=auth_headers(portal_token),
    )
    cross_company_progress = client.get(
        f"/api/v1/portal/campaigns/{other_campaign['id']}/progress",
        headers=auth_headers(portal_token),
    )

    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history) == 1
    assert history[0]["external_document_number"] == "INV-1"
    assert "raw_payload_json" not in history[0]
    assert cross_company_progress.status_code == 404
