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
    phone: str | None = "+998901112233",
    email: str | None = "customer@example.com",
    tax_id: str | None = "123456789",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/customers",
        headers=auth_headers(token),
        json={
            "name": name,
            "phone": phone,
            "email": email,
            "tax_id": tax_id,
            "metadata_json": {"source": "manual"},
        },
    )
    assert response.status_code == 201, response.json()
    return response.json()


def create_sale_record(
    client: TestClient,
    *,
    token: str,
    customer_id: str,
    source_key: str = "manual:sale:1",
    document_kind: str = "sale",
    amount_sign: int = 1,
    gross_amount_minor: int = 10_000_000,
    effective_date: str = "2026-06-15",
    document_status: str = "posted",
    payment_status: str = "paid",
    currency: str = "uzs",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/sale-records",
        headers=auth_headers(token),
        json={
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
            "raw_payload_json": {"example": True},
        },
    )
    assert response.status_code == 201, response.json()
    return response.json()


def test_owner_and_admin_create_customer(client: TestClient) -> None:
    owner = register_company(client)
    admin = create_user_and_login(
        client,
        owner_token=owner["access_token"],
        email="admin@example.com",
        role="admin",
    )

    owner_customer = create_customer(client, token=owner["access_token"])
    admin_customer = create_customer(
        client,
        token=admin["access_token"],
        name="Admin Customer",
        email="admin-customer@example.com",
    )

    assert owner_customer["status"] == "active"
    assert admin_customer["name"] == "Admin Customer"


def test_sales_manager_cannot_create_customer(client: TestClient) -> None:
    owner = register_company(client)
    sales = create_user_and_login(
        client,
        owner_token=owner["access_token"],
        email="sales@example.com",
        role="sales_manager",
    )

    response = client.post(
        "/api/v1/customers",
        headers=auth_headers(sales["access_token"]),
        json={"name": "Blocked"},
    )

    assert response.status_code == 403


def test_customer_list_is_company_scoped_and_filterable(client: TestClient) -> None:
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
    create_customer(
        client,
        token=company_one["access_token"],
        name="Alpha Pharmacy",
        email="alpha@example.com",
        tax_id="AAA",
    )
    create_customer(
        client,
        token=company_two["access_token"],
        name="Beta Pharmacy",
        email="beta@example.com",
        tax_id="BBB",
    )

    response = client.get(
        "/api/v1/customers?search=Alpha",
        headers=auth_headers(company_one["access_token"]),
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "Alpha Pharmacy"


def test_cross_company_customer_returns_404(client: TestClient) -> None:
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

    response = client.get(
        f"/api/v1/customers/{customer['id']}",
        headers=auth_headers(company_two["access_token"]),
    )

    assert response.status_code == 404


def test_update_and_delete_customer(client: TestClient) -> None:
    owner = register_company(client)
    customer = create_customer(client, token=owner["access_token"])

    update_response = client.patch(
        f"/api/v1/customers/{customer['id']}",
        headers=auth_headers(owner["access_token"]),
        json={"name": "Updated Customer", "status": "blocked"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated Customer"
    assert update_response.json()["status"] == "blocked"

    delete_response = client.delete(
        f"/api/v1/customers/{customer['id']}",
        headers=auth_headers(owner["access_token"]),
    )
    assert delete_response.status_code == 204

    get_response = client.get(
        f"/api/v1/customers/{customer['id']}",
        headers=auth_headers(owner["access_token"]),
    )
    assert get_response.status_code == 404


def test_no_auto_merge_by_phone_or_email(client: TestClient) -> None:
    owner = register_company(client)
    first = create_customer(client, token=owner["access_token"], name="First")
    second = create_customer(
        client,
        token=owner["access_token"],
        name="Second",
        phone=first["phone"],
        email=first["email"],
        tax_id="DIFFERENT",
    )

    assert first["id"] != second["id"]


def test_external_refs_validation_and_scoping(client: TestClient) -> None:
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
    customer_one = create_customer(client, token=company_one["access_token"])
    customer_two = create_customer(client, token=company_two["access_token"])

    response = client.post(
        f"/api/v1/customers/{customer_one['id']}/external-refs",
        headers=auth_headers(company_one["access_token"]),
        json={
            "customer_id": customer_one["id"],
            "provider": "moysklad",
            "external_id": "counterparty-1",
            "external_name": "ERP Customer",
            "raw_payload_json": {"id": "counterparty-1"},
        },
    )
    assert response.status_code == 201, response.json()

    duplicate_response = client.post(
        f"/api/v1/customers/{customer_one['id']}/external-refs",
        headers=auth_headers(company_one["access_token"]),
        json={
            "customer_id": customer_one["id"],
            "provider": "moysklad",
            "external_id": "counterparty-1",
        },
    )
    assert duplicate_response.status_code == 409

    other_company_response = client.post(
        f"/api/v1/customers/{customer_two['id']}/external-refs",
        headers=auth_headers(company_two["access_token"]),
        json={
            "customer_id": customer_two["id"],
            "provider": "moysklad",
            "external_id": "counterparty-1",
        },
    )
    assert other_company_response.status_code == 201

    cross_company_customer_response = client.post(
        f"/api/v1/customers/{customer_two['id']}/external-refs",
        headers=auth_headers(company_one["access_token"]),
        json={
            "customer_id": customer_two["id"],
            "provider": "csv",
            "external_id": "csv-1",
        },
    )
    assert cross_company_customer_response.status_code == 404


def test_assignments_business_rules(client: TestClient) -> None:
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
    sales = create_user_and_login(
        client,
        owner_token=company_one["access_token"],
        email="sales@example.com",
        role="sales_manager",
    )
    other_sales = create_user_and_login(
        client,
        owner_token=company_two["access_token"],
        email="other-sales@example.com",
        role="sales_manager",
    )

    assignment_response = client.post(
        f"/api/v1/customers/{customer['id']}/assignments",
        headers=auth_headers(company_one["access_token"]),
        json={"sales_manager_user_id": sales["user"]["id"]},
    )
    assert assignment_response.status_code == 201, assignment_response.json()

    duplicate_response = client.post(
        f"/api/v1/customers/{customer['id']}/assignments",
        headers=auth_headers(company_one["access_token"]),
        json={"sales_manager_user_id": sales["user"]["id"]},
    )
    assert duplicate_response.status_code == 409

    owner_assignment_response = client.post(
        f"/api/v1/customers/{customer['id']}/assignments",
        headers=auth_headers(company_one["access_token"]),
        json={"sales_manager_user_id": company_one["user"]["id"]},
    )
    assert owner_assignment_response.status_code == 422

    other_company_response = client.post(
        f"/api/v1/customers/{customer['id']}/assignments",
        headers=auth_headers(company_one["access_token"]),
        json={"sales_manager_user_id": other_sales["user"]["id"]},
    )
    assert other_company_response.status_code == 404

    unassign_response = client.delete(
        f"/api/v1/customers/{customer['id']}/assignments/{sales['user']['id']}",
        headers=auth_headers(company_one["access_token"]),
    )
    assert unassign_response.status_code == 204


def test_create_sale_record_and_validation(client: TestClient) -> None:
    owner = register_company(client)
    customer = create_customer(client, token=owner["access_token"])

    sale = create_sale_record(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
    )
    assert sale["currency"] == "UZS"
    assert sale["amount_sign"] == 1
    assert "raw_payload_json" not in sale

    duplicate_response = client.post(
        "/api/v1/sale-records",
        headers=auth_headers(owner["access_token"]),
        json={
            "customer_id": customer["id"],
            "source_type": "manual",
            "source_key": "manual:sale:1",
            "provider": "manual",
            "document_kind": "sale",
            "document_date": "2026-06-15",
            "effective_date": "2026-06-15",
            "gross_amount_minor": 1,
            "amount_sign": 1,
            "currency": "UZS",
            "currency_scale": 0,
            "payment_status": "paid",
            "document_status": "posted",
        },
    )
    assert duplicate_response.status_code == 409

    negative_response = client.post(
        "/api/v1/sale-records",
        headers=auth_headers(owner["access_token"]),
        json={
            "customer_id": customer["id"],
            "source_type": "manual",
            "source_key": "manual:negative",
            "provider": "manual",
            "document_kind": "sale",
            "document_date": "2026-06-15",
            "effective_date": "2026-06-15",
            "gross_amount_minor": -1,
            "amount_sign": 1,
            "currency": "UZS",
            "currency_scale": 0,
            "payment_status": "paid",
            "document_status": "posted",
        },
    )
    assert negative_response.status_code == 422

    bad_sign_response = client.post(
        "/api/v1/sale-records",
        headers=auth_headers(owner["access_token"]),
        json={
            "customer_id": customer["id"],
            "source_type": "manual",
            "source_key": "manual:bad-sign",
            "provider": "manual",
            "document_kind": "sale",
            "document_date": "2026-06-15",
            "effective_date": "2026-06-15",
            "gross_amount_minor": 100,
            "amount_sign": 0,
            "currency": "UZS",
            "currency_scale": 0,
            "payment_status": "paid",
            "document_status": "posted",
        },
    )
    assert bad_sign_response.status_code == 422


def test_return_refund_negative_sign_accepted(client: TestClient) -> None:
    owner = register_company(client)
    customer = create_customer(client, token=owner["access_token"])

    sale_return = create_sale_record(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        source_key="manual:return:1",
        document_kind="return",
        amount_sign=-1,
    )
    refund = create_sale_record(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        source_key="manual:refund:1",
        document_kind="refund",
        amount_sign=-1,
    )

    assert sale_return["amount_sign"] == -1
    assert refund["document_kind"] == "refund"


def test_same_sale_source_key_allowed_in_different_company(client: TestClient) -> None:
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
    customer_one = create_customer(client, token=company_one["access_token"])
    customer_two = create_customer(client, token=company_two["access_token"])

    sale_one = create_sale_record(
        client,
        token=company_one["access_token"],
        customer_id=customer_one["id"],
        source_key="shared-key",
    )
    sale_two = create_sale_record(
        client,
        token=company_two["access_token"],
        customer_id=customer_two["id"],
        source_key="shared-key",
    )

    assert sale_one["id"] != sale_two["id"]


def test_sale_customer_must_belong_to_same_company(client: TestClient) -> None:
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
    other_customer = create_customer(client, token=company_two["access_token"])

    response = client.post(
        "/api/v1/sale-records",
        headers=auth_headers(company_one["access_token"]),
        json={
            "customer_id": other_customer["id"],
            "source_type": "manual",
            "source_key": "manual:foreign-customer",
            "provider": "manual",
            "document_kind": "sale",
            "document_date": "2026-06-15",
            "effective_date": "2026-06-15",
            "gross_amount_minor": 100,
            "amount_sign": 1,
            "currency": "UZS",
            "currency_scale": 0,
            "payment_status": "paid",
            "document_status": "posted",
        },
    )

    assert response.status_code == 404


def test_sale_records_list_filters_and_cross_company_access(client: TestClient) -> None:
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
    customer_one = create_customer(client, token=company_one["access_token"])
    customer_two = create_customer(client, token=company_two["access_token"])
    sale = create_sale_record(
        client,
        token=company_one["access_token"],
        customer_id=customer_one["id"],
        source_key="posted-paid",
        effective_date="2026-06-15",
        document_status="posted",
    )
    create_sale_record(
        client,
        token=company_one["access_token"],
        customer_id=customer_one["id"],
        source_key="cancelled",
        effective_date="2026-07-15",
        document_status="cancelled",
    )
    create_sale_record(
        client,
        token=company_two["access_token"],
        customer_id=customer_two["id"],
        source_key="other-company",
    )

    list_response = client.get(
        "/api/v1/sale-records"
        f"?customer_id={customer_one['id']}"
        "&document_status=posted"
        "&effective_date_from=2026-06-01"
        "&effective_date_to=2026-06-30",
        headers=auth_headers(company_one["access_token"]),
    )
    cross_response = client.get(
        f"/api/v1/sale-records/{sale['id']}",
        headers=auth_headers(company_two["access_token"]),
    )

    assert list_response.status_code == 200
    assert [item["source_key"] for item in list_response.json()["items"]] == [
        "posted-paid"
    ]
    assert cross_response.status_code == 404


def test_sales_manager_read_only_for_customers_and_sales(client: TestClient) -> None:
    owner = register_company(client)
    sales = create_user_and_login(
        client,
        owner_token=owner["access_token"],
        email="sales@example.com",
        role="sales_manager",
    )
    customer = create_customer(client, token=owner["access_token"])
    create_sale_record(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
    )

    customer_read = client.get(
        "/api/v1/customers",
        headers=auth_headers(sales["access_token"]),
    )
    sale_read = client.get(
        "/api/v1/sale-records",
        headers=auth_headers(sales["access_token"]),
    )
    customer_write = client.post(
        "/api/v1/customers",
        headers=auth_headers(sales["access_token"]),
        json={"name": "Blocked"},
    )
    sale_write = client.post(
        "/api/v1/sale-records",
        headers=auth_headers(sales["access_token"]),
        json={},
    )

    assert customer_read.status_code == 200
    assert sale_read.status_code == 200
    assert customer_write.status_code == 403
    assert sale_write.status_code == 403

