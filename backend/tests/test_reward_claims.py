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
    title: str = "Rewards",
    allow_claims: bool = True,
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/campaigns",
        headers=auth_headers(token),
        json={
            "title": title,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "currency": "UZS",
            "allow_claims": allow_claims,
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
    stock_tracking_mode: str = "none",
    stock_quantity: int | None = None,
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


def complete_campaign(
    client: TestClient,
    *,
    token: str,
    campaign_id: str,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/campaigns/{campaign_id}/complete",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.json()
    return response.json()


def create_sale(
    client: TestClient,
    *,
    token: str,
    customer_id: str,
    source_key: str,
    amount: int,
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
    assert response.status_code == 201, response.json()
    return response.json()


def recalc_customer(
    client: TestClient,
    *,
    token: str,
    campaign_id: str,
    customer_id: str,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/progress/campaigns/{campaign_id}/customers/{customer_id}/recalculate",
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


def portal_token_for_customer(
    client: TestClient,
    *,
    owner_token: str,
    customer_id: str,
) -> str:
    magic_link = create_magic_link(
        client,
        token=owner_token,
        customer_id=customer_id,
    )
    response = client.post(
        "/api/v1/portal/session",
        json={"token": magic_link["raw_token"]},
    )
    assert response.status_code == 200, response.json()
    return response.json()["portal_access_token"]


def setup_claimable_campaign(
    client: TestClient,
    *,
    slug: str = "acme",
    owner_email: str = "owner@example.com",
    amount: int = 35_000_000,
    stock_tracking_mode: str = "none",
    stock_quantity: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    owner = register_company(client, slug=slug, owner_email=owner_email)
    customer = create_customer(client, token=owner["access_token"])
    campaign = create_campaign(client, token=owner["access_token"])
    tiers = [
        create_tier(
            client,
            token=owner["access_token"],
            campaign_id=campaign["id"],
            title="Powerbank",
            amount=10_000_000,
        ),
        create_tier(
            client,
            token=owner["access_token"],
            campaign_id=campaign["id"],
            title="AirPods",
            amount=30_000_000,
            stock_tracking_mode=stock_tracking_mode,
            stock_quantity=stock_quantity,
        ),
        create_tier(
            client,
            token=owner["access_token"],
            campaign_id=campaign["id"],
            title="Smart Watch",
            amount=50_000_000,
        ),
    ]
    activate_campaign(client, token=owner["access_token"], campaign_id=campaign["id"])
    create_sale(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        source_key=f"sale-{customer['id']}",
        amount=amount,
    )
    recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
    )
    return owner, campaign, customer, tiers


def admin_create_claim(
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
            "customer_comment": "Please prepare this gift.",
        },
    )
    assert response.status_code == 201, response.json()
    return response.json()


def get_tier(
    client: TestClient,
    *,
    token: str,
    campaign_id: str,
    tier_id: str,
) -> dict[str, Any]:
    response = client.get(
        f"/api/v1/campaigns/{campaign_id}/gift-tiers/{tier_id}",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.json()
    return response.json()


def test_portal_customer_can_claim_reached_tier_and_list_own_claims(
    client: TestClient,
) -> None:
    owner, campaign, customer, tiers = setup_claimable_campaign(client)
    portal_token = portal_token_for_customer(
        client,
        owner_token=owner["access_token"],
        customer_id=customer["id"],
    )

    create_response = client.post(
        f"/api/v1/portal/campaigns/{campaign['id']}/claims",
        headers=auth_headers(portal_token),
        json={
            "gift_tier_id": tiers[1]["id"],
            "customer_comment": "I choose AirPods.",
        },
    )
    list_response = client.get(
        "/api/v1/portal/claims",
        headers=auth_headers(portal_token),
    )
    duplicate_response = client.post(
        f"/api/v1/portal/campaigns/{campaign['id']}/claims",
        headers=auth_headers(portal_token),
        json={"gift_tier_id": tiers[0]["id"]},
    )

    assert create_response.status_code == 201, create_response.json()
    claim = create_response.json()
    assert claim["status"] == "pending"
    assert claim["customer_id"] == customer["id"]
    assert claim["gift_tier_id"] == tiers[1]["id"]
    assert "token_hash" not in claim
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [claim["id"]]
    assert duplicate_response.status_code == 409


def test_claim_creation_business_rules(client: TestClient) -> None:
    owner, campaign, customer, tiers = setup_claimable_campaign(
        client,
        amount=35_000_000,
    )
    unreached = client.post(
        "/api/v1/reward-claims",
        headers=auth_headers(owner["access_token"]),
        json={
            "campaign_id": campaign["id"],
            "customer_id": customer["id"],
            "gift_tier_id": tiers[2]["id"],
        },
    )
    assert unreached.status_code == 409

    disabled_campaign = create_campaign(
        client,
        token=owner["access_token"],
        title="No Claims",
        allow_claims=False,
    )
    disabled_tier = create_tier(
        client,
        token=owner["access_token"],
        campaign_id=disabled_campaign["id"],
        title="Gift",
        amount=10_000_000,
    )
    activate_campaign(
        client,
        token=owner["access_token"],
        campaign_id=disabled_campaign["id"],
    )
    recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=disabled_campaign["id"],
        customer_id=customer["id"],
    )
    disabled = client.post(
        "/api/v1/reward-claims",
        headers=auth_headers(owner["access_token"]),
        json={
            "campaign_id": disabled_campaign["id"],
            "customer_id": customer["id"],
            "gift_tier_id": disabled_tier["id"],
        },
    )
    assert disabled.status_code == 409

    draft_campaign = create_campaign(
        client,
        token=owner["access_token"],
        title="Draft Claims",
    )
    draft_tier = create_tier(
        client,
        token=owner["access_token"],
        campaign_id=draft_campaign["id"],
        title="Draft Gift",
        amount=10_000_000,
    )
    recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=draft_campaign["id"],
        customer_id=customer["id"],
    )
    draft = client.post(
        "/api/v1/reward-claims",
        headers=auth_headers(owner["access_token"]),
        json={
            "campaign_id": draft_campaign["id"],
            "customer_id": customer["id"],
            "gift_tier_id": draft_tier["id"],
        },
    )
    assert draft.status_code == 409

    completed_campaign = create_campaign(
        client,
        token=owner["access_token"],
        title="Completed Claims",
    )
    completed_tier = create_tier(
        client,
        token=owner["access_token"],
        campaign_id=completed_campaign["id"],
        title="Completed Gift",
        amount=10_000_000,
    )
    activate_campaign(
        client,
        token=owner["access_token"],
        campaign_id=completed_campaign["id"],
    )
    complete_campaign(
        client,
        token=owner["access_token"],
        campaign_id=completed_campaign["id"],
    )
    recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=completed_campaign["id"],
        customer_id=customer["id"],
    )
    completed = admin_create_claim(
        client,
        token=owner["access_token"],
        campaign_id=completed_campaign["id"],
        customer_id=customer["id"],
        gift_tier_id=completed_tier["id"],
    )
    assert completed["status"] == "pending"


def test_admin_rbac_and_auth_boundaries(client: TestClient) -> None:
    owner, campaign, customer, tiers = setup_claimable_campaign(client)
    sales = create_user_and_login(
        client,
        owner_token=owner["access_token"],
        email="sales@example.com",
        role="sales_manager",
    )
    portal_token = portal_token_for_customer(
        client,
        owner_token=owner["access_token"],
        customer_id=customer["id"],
    )

    sales_create = client.post(
        "/api/v1/reward-claims",
        headers=auth_headers(sales["access_token"]),
        json={
            "campaign_id": campaign["id"],
            "customer_id": customer["id"],
            "gift_tier_id": tiers[1]["id"],
        },
    )
    owner_claim = admin_create_claim(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
        gift_tier_id=tiers[1]["id"],
    )
    sales_read = client.get(
        f"/api/v1/reward-claims/{owner_claim['id']}",
        headers=auth_headers(sales["access_token"]),
    )
    admin_on_portal = client.get(
        "/api/v1/portal/claims",
        headers=auth_headers(owner["access_token"]),
    )
    portal_on_admin = client.get(
        "/api/v1/reward-claims",
        headers=auth_headers(portal_token),
    )
    unauthenticated = client.get("/api/v1/reward-claims")

    assert sales_create.status_code == 403
    assert sales_read.status_code == 200
    assert admin_on_portal.status_code == 401
    assert portal_on_admin.status_code == 401
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["request_id"]


def test_claims_are_company_scoped(client: TestClient) -> None:
    company_one, campaign, customer, tiers = setup_claimable_campaign(client)
    company_two = register_company(
        client,
        slug="company-two",
        owner_email="two@example.com",
    )
    claim = admin_create_claim(
        client,
        token=company_one["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
        gift_tier_id=tiers[1]["id"],
    )

    cross_get = client.get(
        f"/api/v1/reward-claims/{claim['id']}",
        headers=auth_headers(company_two["access_token"]),
    )
    cross_create = client.post(
        "/api/v1/reward-claims",
        headers=auth_headers(company_two["access_token"]),
        json={
            "campaign_id": campaign["id"],
            "customer_id": customer["id"],
            "gift_tier_id": tiers[1]["id"],
        },
    )

    assert cross_get.status_code == 404
    assert cross_create.status_code == 404


def test_stock_reservation_modes(client: TestClient) -> None:
    none_owner, none_campaign, none_customer, none_tiers = setup_claimable_campaign(
        client,
        slug="none-stock",
        owner_email="none@example.com",
    )
    none_claim = admin_create_claim(
        client,
        token=none_owner["access_token"],
        campaign_id=none_campaign["id"],
        customer_id=none_customer["id"],
        gift_tier_id=none_tiers[1]["id"],
    )
    approve_none = client.post(
        f"/api/v1/reward-claims/{none_claim['id']}/approve",
        headers=auth_headers(none_owner["access_token"]),
        json={"admin_comment": "Approved"},
    )
    none_tier = get_tier(
        client,
        token=none_owner["access_token"],
        campaign_id=none_campaign["id"],
        tier_id=none_tiers[1]["id"],
    )
    assert approve_none.status_code == 200
    assert none_tier["reserved_quantity"] == 0
    assert none_tier["fulfilled_quantity"] == 0

    strict_owner, strict_campaign, strict_customer, strict_tiers = (
        setup_claimable_campaign(
            client,
            slug="strict-stock",
            owner_email="strict@example.com",
            stock_tracking_mode="strict",
            stock_quantity=1,
        )
    )
    strict_claim = admin_create_claim(
        client,
        token=strict_owner["access_token"],
        campaign_id=strict_campaign["id"],
        customer_id=strict_customer["id"],
        gift_tier_id=strict_tiers[1]["id"],
    )
    approve_strict = client.post(
        f"/api/v1/reward-claims/{strict_claim['id']}/approve",
        headers=auth_headers(strict_owner["access_token"]),
        json={},
    )
    strict_tier_after_approve = get_tier(
        client,
        token=strict_owner["access_token"],
        campaign_id=strict_campaign["id"],
        tier_id=strict_tiers[1]["id"],
    )
    fulfill_strict = client.post(
        f"/api/v1/reward-claims/{strict_claim['id']}/fulfill",
        headers=auth_headers(strict_owner["access_token"]),
        json={},
    )
    strict_tier_after_fulfill = get_tier(
        client,
        token=strict_owner["access_token"],
        campaign_id=strict_campaign["id"],
        tier_id=strict_tiers[1]["id"],
    )
    assert approve_strict.status_code == 200
    assert strict_tier_after_approve["reserved_quantity"] == 1
    assert strict_tier_after_approve["available_quantity"] == 0
    assert fulfill_strict.status_code == 200
    assert strict_tier_after_fulfill["reserved_quantity"] == 0
    assert strict_tier_after_fulfill["fulfilled_quantity"] == 1

    no_stock_owner, no_stock_campaign, no_stock_customer, no_stock_tiers = (
        setup_claimable_campaign(
            client,
            slug="no-stock",
            owner_email="no-stock@example.com",
            stock_tracking_mode="strict",
            stock_quantity=0,
        )
    )
    no_stock_claim = admin_create_claim(
        client,
        token=no_stock_owner["access_token"],
        campaign_id=no_stock_campaign["id"],
        customer_id=no_stock_customer["id"],
        gift_tier_id=no_stock_tiers[1]["id"],
    )
    no_stock_approve = client.post(
        f"/api/v1/reward-claims/{no_stock_claim['id']}/approve",
        headers=auth_headers(no_stock_owner["access_token"]),
        json={},
    )
    assert no_stock_approve.status_code == 409

    soft_owner, soft_campaign, soft_customer, soft_tiers = setup_claimable_campaign(
        client,
        slug="soft-stock",
        owner_email="soft@example.com",
        stock_tracking_mode="soft",
        stock_quantity=0,
    )
    soft_claim = admin_create_claim(
        client,
        token=soft_owner["access_token"],
        campaign_id=soft_campaign["id"],
        customer_id=soft_customer["id"],
        gift_tier_id=soft_tiers[1]["id"],
    )
    soft_approve = client.post(
        f"/api/v1/reward-claims/{soft_claim['id']}/approve",
        headers=auth_headers(soft_owner["access_token"]),
        json={},
    )
    soft_tier = get_tier(
        client,
        token=soft_owner["access_token"],
        campaign_id=soft_campaign["id"],
        tier_id=soft_tiers[1]["id"],
    )
    assert soft_approve.status_code == 200
    assert soft_tier["reserved_quantity"] == 1
    assert soft_tier["available_quantity"] == -1


def test_lifecycle_reject_cancel_and_invalid_transitions(client: TestClient) -> None:
    owner, campaign, customer, tiers = setup_claimable_campaign(
        client,
        stock_tracking_mode="strict",
        stock_quantity=3,
    )
    claim = admin_create_claim(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
        gift_tier_id=tiers[1]["id"],
    )
    fulfill_pending = client.post(
        f"/api/v1/reward-claims/{claim['id']}/fulfill",
        headers=auth_headers(owner["access_token"]),
        json={},
    )
    assert fulfill_pending.status_code == 409

    approve = client.post(
        f"/api/v1/reward-claims/{claim['id']}/approve",
        headers=auth_headers(owner["access_token"]),
        json={},
    )
    reject = client.post(
        f"/api/v1/reward-claims/{claim['id']}/reject",
        headers=auth_headers(owner["access_token"]),
        json={"admin_comment": "Not available"},
    )
    tier_after_reject = get_tier(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        tier_id=tiers[1]["id"],
    )
    approve_rejected = client.post(
        f"/api/v1/reward-claims/{claim['id']}/approve",
        headers=auth_headers(owner["access_token"]),
        json={},
    )
    cancel_rejected = client.post(
        f"/api/v1/reward-claims/{claim['id']}/cancel",
        headers=auth_headers(owner["access_token"]),
        json={},
    )
    assert approve.status_code == 200
    assert reject.status_code == 200
    assert reject.json()["status"] == "rejected"
    assert tier_after_reject["reserved_quantity"] == 0
    assert approve_rejected.status_code == 409
    assert cancel_rejected.status_code == 409

    claim_to_cancel = admin_create_claim(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
        gift_tier_id=tiers[1]["id"],
    )
    client.post(
        f"/api/v1/reward-claims/{claim_to_cancel['id']}/approve",
        headers=auth_headers(owner["access_token"]),
        json={},
    )
    cancel_approved = client.post(
        f"/api/v1/reward-claims/{claim_to_cancel['id']}/cancel",
        headers=auth_headers(owner["access_token"]),
        json={},
    )
    tier_after_cancel = get_tier(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        tier_id=tiers[1]["id"],
    )
    assert cancel_approved.status_code == 200
    assert cancel_approved.json()["status"] == "cancelled"
    assert tier_after_cancel["reserved_quantity"] == 0

    portal_claim = admin_create_claim(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
        gift_tier_id=tiers[1]["id"],
    )
    portal_token = portal_token_for_customer(
        client,
        owner_token=owner["access_token"],
        customer_id=customer["id"],
    )
    portal_cancel = client.post(
        f"/api/v1/portal/claims/{portal_claim['id']}/cancel",
        headers=auth_headers(portal_token),
    )
    assert portal_cancel.status_code == 200
    assert portal_cancel.json()["status"] == "cancelled"

    fulfilled_claim = admin_create_claim(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
        gift_tier_id=tiers[1]["id"],
    )
    client.post(
        f"/api/v1/reward-claims/{fulfilled_claim['id']}/approve",
        headers=auth_headers(owner["access_token"]),
        json={},
    )
    fulfilled = client.post(
        f"/api/v1/reward-claims/{fulfilled_claim['id']}/fulfill",
        headers=auth_headers(owner["access_token"]),
        json={},
    )
    cancel_fulfilled = client.post(
        f"/api/v1/reward-claims/{fulfilled_claim['id']}/cancel",
        headers=auth_headers(owner["access_token"]),
        json={},
    )
    assert fulfilled.status_code == 200
    assert fulfilled.json()["status"] == "fulfilled"
    assert cancel_fulfilled.status_code == 409
