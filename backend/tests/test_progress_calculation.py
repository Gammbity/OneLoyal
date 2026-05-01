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
    title: str = "Rewards",
    currency: str = "UZS",
    rules_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/campaigns",
        headers=auth_headers(token),
        json={
            "title": title,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "currency": currency,
            "rules_json": rules_json or {},
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
    is_active: bool = True,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/campaigns/{campaign_id}/gift-tiers",
        headers=auth_headers(token),
        json={
            "title": title,
            "required_amount_minor": amount,
            "is_active": is_active,
        },
    )
    assert response.status_code == 201, response.json()
    return response.json()


def create_default_tiers(
    client: TestClient,
    *,
    token: str,
    campaign_id: str,
) -> list[dict[str, Any]]:
    return [
        create_tier(
            client,
            token=token,
            campaign_id=campaign_id,
            title="Powerbank",
            amount=10_000_000,
        ),
        create_tier(
            client,
            token=token,
            campaign_id=campaign_id,
            title="AirPods",
            amount=30_000_000,
        ),
        create_tier(
            client,
            token=token,
            campaign_id=campaign_id,
            title="Smart Watch",
            amount=50_000_000,
        ),
    ]


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


def create_sale(
    client: TestClient,
    *,
    token: str,
    customer_id: str,
    source_key: str,
    gross_amount_minor: int,
    document_kind: str = "sale",
    amount_sign: int = 1,
    currency: str = "UZS",
    document_status: str = "posted",
    payment_status: str = "paid",
    effective_date: str = "2026-06-01",
    net_amount_minor: int | None = None,
    paid_amount_minor: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "customer_id": customer_id,
        "source_type": "manual",
        "source_key": source_key,
        "provider": "manual",
        "document_kind": document_kind,
        "document_date": effective_date,
        "effective_date": effective_date,
        "gross_amount_minor": gross_amount_minor,
        "amount_sign": amount_sign,
        "currency": currency,
        "currency_scale": 0,
        "payment_status": payment_status,
        "document_status": document_status,
    }
    if net_amount_minor is not None:
        payload["net_amount_minor"] = net_amount_minor
    if paid_amount_minor is not None:
        payload["paid_amount_minor"] = paid_amount_minor

    response = client.post(
        "/api/v1/sale-records",
        headers=auth_headers(token),
        json=payload,
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


def setup_campaign_customer(
    client: TestClient,
    *,
    rules_json: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    owner = register_company(client)
    campaign = create_campaign(
        client,
        token=owner["access_token"],
        rules_json=rules_json,
    )
    tiers = create_default_tiers(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
    )
    customer = create_customer(client, token=owner["access_token"])
    return owner, campaign, customer, tiers


def test_no_sales_and_no_tiers_edge_cases(client: TestClient) -> None:
    owner = register_company(client)
    no_tier_campaign = create_campaign(client, token=owner["access_token"])
    customer = create_customer(client, token=owner["access_token"])

    no_tiers = recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=no_tier_campaign["id"],
        customer_id=customer["id"],
    )
    assert no_tiers["total_amount_minor"] == 0
    assert no_tiers["current_tier_id"] is None
    assert no_tiers["next_tier_id"] is None
    assert no_tiers["amount_left_minor"] == 0
    assert no_tiers["progress_percent_basis_points"] == 0
    assert no_tiers["stats_json"]["no_tiers"] is True

    campaign = create_campaign(client, token=owner["access_token"], title="With Tiers")
    first = create_tier(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        title="Powerbank",
        amount=10_000_000,
    )
    no_sales = recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
    )
    assert no_sales["total_amount_minor"] == 0
    assert no_sales["next_tier_id"] == first["id"]
    assert no_sales["amount_left_minor"] == 10_000_000
    assert no_sales["progress_percent"] == "0.00"


def test_tier_progress_boundaries(client: TestClient) -> None:
    owner, campaign, customer, tiers = setup_campaign_customer(client)

    create_sale(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        source_key="below",
        gross_amount_minor=5_000_000,
    )
    below = recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
    )
    assert below["current_tier_id"] is None
    assert below["next_tier_id"] == tiers[0]["id"]
    assert below["amount_left_minor"] == 5_000_000
    assert below["progress_percent_basis_points"] == 5000

    create_sale(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        source_key="exact-first",
        gross_amount_minor=5_000_000,
    )
    exact_first = recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
    )
    assert exact_first["current_tier_id"] == tiers[0]["id"]
    assert exact_first["next_tier_id"] == tiers[1]["id"]
    assert exact_first["progress_percent_basis_points"] == 0

    create_sale(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        source_key="between",
        gross_amount_minor=10_000_000,
    )
    between = recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
    )
    assert between["current_tier_id"] == tiers[0]["id"]
    assert between["next_tier_id"] == tiers[1]["id"]
    assert between["amount_left_minor"] == 10_000_000
    assert between["progress_percent_basis_points"] == 5000

    create_sale(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        source_key="exact-middle",
        gross_amount_minor=10_000_000,
    )
    exact_middle = recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
    )
    assert exact_middle["current_tier_id"] == tiers[1]["id"]
    assert exact_middle["next_tier_id"] == tiers[2]["id"]
    assert exact_middle["progress_percent_basis_points"] == 0

    create_sale(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        source_key="above-highest",
        gross_amount_minor=25_000_000,
    )
    above_highest = recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
    )
    assert above_highest["current_tier_id"] == tiers[2]["id"]
    assert above_highest["next_tier_id"] is None
    assert above_highest["amount_left_minor"] == 0
    assert above_highest["progress_percent_basis_points"] == 10000


def test_returns_refunds_and_clamp_to_zero(client: TestClient) -> None:
    owner, campaign, customer, _ = setup_campaign_customer(client)
    create_sale(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        source_key="sale",
        gross_amount_minor=5_000_000,
    )
    create_sale(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        source_key="return",
        gross_amount_minor=8_000_000,
        document_kind="return",
        amount_sign=-1,
    )
    progress = recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
    )
    assert progress["total_amount_minor"] == 0


def test_document_status_and_payment_rules(client: TestClient) -> None:
    owner, campaign, customer, _ = setup_campaign_customer(client)
    create_sale(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        source_key="cancelled",
        gross_amount_minor=10_000_000,
        document_status="cancelled",
    )
    create_sale(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        source_key="deleted",
        gross_amount_minor=10_000_000,
        document_status="deleted",
    )
    create_sale(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        source_key="unpaid",
        gross_amount_minor=10_000_000,
        payment_status="unpaid",
    )
    default_progress = recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
    )
    assert default_progress["total_amount_minor"] == 10_000_000
    assert default_progress["stats_json"]["excluded_cancelled_count"] == 1
    assert default_progress["stats_json"]["excluded_deleted_count"] == 1

    paid_only_campaign = create_campaign(
        client,
        token=owner["access_token"],
        title="Paid Only",
        rules_json={"payment_rule": "paid_only"},
    )
    create_default_tiers(
        client,
        token=owner["access_token"],
        campaign_id=paid_only_campaign["id"],
    )
    paid_only = recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=paid_only_campaign["id"],
        customer_id=customer["id"],
    )
    assert paid_only["total_amount_minor"] == 0
    assert paid_only["stats_json"]["excluded_unpaid_count"] == 1


def test_paid_amount_and_net_amount_rules(client: TestClient) -> None:
    owner, paid_campaign, customer, _ = setup_campaign_customer(
        client,
        rules_json={"payment_rule": "paid_amount_only"},
    )
    create_sale(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        source_key="paid-amount",
        gross_amount_minor=10_000_000,
        paid_amount_minor=4_000_000,
        payment_status="partial",
    )
    paid_progress = recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=paid_campaign["id"],
        customer_id=customer["id"],
    )
    assert paid_progress["total_amount_minor"] == 4_000_000

    net_campaign = create_campaign(
        client,
        token=owner["access_token"],
        title="Net Campaign",
        rules_json={"amount_basis": "net"},
    )
    create_default_tiers(
        client,
        token=owner["access_token"],
        campaign_id=net_campaign["id"],
    )
    net_customer = create_customer(
        client,
        token=owner["access_token"],
        name="Net Customer",
        email="net@example.com",
    )
    create_sale(
        client,
        token=owner["access_token"],
        customer_id=net_customer["id"],
        source_key="net",
        gross_amount_minor=10_000_000,
        net_amount_minor=8_000_000,
    )
    create_sale(
        client,
        token=owner["access_token"],
        customer_id=net_customer["id"],
        source_key="net-fallback",
        gross_amount_minor=2_000_000,
    )
    net_progress = recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=net_campaign["id"],
        customer_id=net_customer["id"],
    )
    assert net_progress["total_amount_minor"] == 10_000_000


def test_currency_mismatch_exclude_and_fail(client: TestClient) -> None:
    owner, campaign, customer, _ = setup_campaign_customer(client)
    create_sale(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        source_key="usd-sale",
        gross_amount_minor=10_000_000,
        currency="USD",
    )
    excluded = recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
    )
    assert excluded["total_amount_minor"] == 0
    assert excluded["stats_json"]["excluded_currency_mismatch_count"] == 1

    fail_campaign = create_campaign(
        client,
        token=owner["access_token"],
        title="Fail Currency",
        rules_json={"currency_mismatch_policy": "fail"},
    )
    create_default_tiers(
        client,
        token=owner["access_token"],
        campaign_id=fail_campaign["id"],
    )
    response = client.post(
        f"/api/v1/progress/campaigns/{fail_campaign['id']}"
        f"/customers/{customer['id']}/recalculate",
        headers=auth_headers(owner["access_token"]),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_date_filtering_and_inactive_tiers(client: TestClient) -> None:
    owner = register_company(client)
    campaign = create_campaign(client, token=owner["access_token"])
    inactive = create_tier(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        title="Inactive Low",
        amount=10_000_000,
        is_active=False,
    )
    active = create_tier(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        title="Active High",
        amount=30_000_000,
    )
    customer = create_customer(client, token=owner["access_token"])
    create_sale(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        source_key="inside",
        gross_amount_minor=20_000_000,
        effective_date="2026-06-01",
    )
    create_sale(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        source_key="outside",
        gross_amount_minor=100_000_000,
        effective_date="2027-01-01",
    )
    progress = recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
    )
    assert progress["total_amount_minor"] == 20_000_000
    assert progress["current_tier_id"] is None
    assert progress["next_tier_id"] == active["id"]
    assert progress["next_tier_id"] != inactive["id"]
    assert progress["progress_percent_basis_points"] == 6667


def test_progress_upsert_updates_existing_row(client: TestClient) -> None:
    owner, campaign, customer, _ = setup_campaign_customer(client)
    create_sale(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        source_key="first",
        gross_amount_minor=10_000_000,
    )
    first_progress = recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
    )
    create_sale(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        source_key="second",
        gross_amount_minor=20_000_000,
    )
    second_progress = recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
    )
    assert second_progress["id"] == first_progress["id"]
    assert second_progress["total_amount_minor"] == 30_000_000


def test_campaign_recalculation_batch_and_list_filters(client: TestClient) -> None:
    owner = register_company(client)
    campaign = create_campaign(client, token=owner["access_token"])
    tiers = create_default_tiers(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
    )
    first_customer = create_customer(
        client,
        token=owner["access_token"],
        name="Alpha",
        email="alpha@example.com",
    )
    second_customer = create_customer(
        client,
        token=owner["access_token"],
        name="Beta",
        email="beta@example.com",
    )
    no_sale_customer = create_customer(
        client,
        token=owner["access_token"],
        name="No Sale",
        email="nosale@example.com",
    )
    create_sale(
        client,
        token=owner["access_token"],
        customer_id=first_customer["id"],
        source_key="alpha-sale",
        gross_amount_minor=12_000_000,
    )
    create_sale(
        client,
        token=owner["access_token"],
        customer_id=second_customer["id"],
        source_key="beta-sale",
        gross_amount_minor=35_000_000,
    )
    response = client.post(
        f"/api/v1/progress/campaigns/{campaign['id']}/recalculate",
        headers=auth_headers(owner["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["affected_customer_count"] == 2
    assert response.json()["recalculated_count"] == 2

    list_response = client.get(
        f"/api/v1/progress/campaigns/{campaign['id']}"
        f"?current_tier_id={tiers[0]['id']}&search=Alpha",
        headers=auth_headers(owner["access_token"]),
    )
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert len(items) == 1
    assert items[0]["customer_id"] == first_customer["id"]
    assert items[0]["customer_name"] == "Alpha"

    missing_response = client.get(
        f"/api/v1/progress/campaigns/{campaign['id']}"
        f"/customers/{no_sale_customer['id']}",
        headers=auth_headers(owner["access_token"]),
    )
    assert missing_response.status_code == 404


def test_progress_rbac_and_company_scoping(client: TestClient) -> None:
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
    campaign = create_campaign(client, token=company_one["access_token"])
    create_default_tiers(
        client,
        token=company_one["access_token"],
        campaign_id=campaign["id"],
    )
    customer = create_customer(client, token=company_one["access_token"])
    create_sale(
        client,
        token=company_one["access_token"],
        customer_id=customer["id"],
        source_key="sale",
        gross_amount_minor=10_000_000,
    )
    recalc_customer(
        client,
        token=company_one["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
    )

    sales_recalculate = client.post(
        f"/api/v1/progress/campaigns/{campaign['id']}/recalculate",
        headers=auth_headers(sales["access_token"]),
    )
    sales_read = client.get(
        f"/api/v1/progress/campaigns/{campaign['id']}/customers/{customer['id']}",
        headers=auth_headers(sales["access_token"]),
    )
    cross_company = client.get(
        f"/api/v1/progress/campaigns/{campaign['id']}/customers/{customer['id']}",
        headers=auth_headers(company_two["access_token"]),
    )
    unauthenticated = client.get(
        f"/api/v1/progress/campaigns/{campaign['id']}/customers/{customer['id']}"
    )

    assert sales_recalculate.status_code == 403
    assert sales_read.status_code == 200
    assert cross_company.status_code == 404
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["request_id"]
