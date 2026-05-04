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


def preview_csv(
    client: TestClient,
    *,
    token: str,
    csv_text: str,
    filename: str = "import.csv",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/imports/csv/preview",
        headers=auth_headers(token),
        files={"file": (filename, csv_text.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 201, response.json()
    return response.json()


def commit_batch(client: TestClient, *, token: str, batch_id: str) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/imports/{batch_id}/commit",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.json()
    return response.json()


def valid_csv(
    *,
    customer_external_id: str = "cust_1",
    sale_external_id: str = "sale_1",
    amount: str = "30000000",
    customer_name: str = "CSV Customer",
    document_kind: str = "sale",
    phone: str = "+998901234567",
    email: str = "csv@example.com",
) -> str:
    return (
        "customer_external_id,customer_name,sale_date,amount,currency,"
        "sale_external_id,document_number,document_kind,payment_status,"
        "document_status,phone,email\n"
        f"{customer_external_id},{customer_name},2026-06-15,{amount},UZS,"
        f"{sale_external_id},INV-1,{document_kind},paid,posted,{phone},{email}\n"
    )


def create_active_campaign(client: TestClient, *, token: str) -> dict[str, Any]:
    campaign_response = client.post(
        "/api/v1/campaigns",
        headers=auth_headers(token),
        json={
            "title": "CSV Campaign",
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


def test_owner_admin_preview_and_sales_manager_rejected(client: TestClient) -> None:
    owner = register_company(client)
    admin = create_user_and_login(
        client,
        owner_token=owner["access_token"],
        email="admin@example.com",
        role="admin",
    )
    sales = create_user_and_login(
        client,
        owner_token=owner["access_token"],
        email="sales@example.com",
        role="sales_manager",
    )

    owner_preview = preview_csv(
        client,
        token=owner["access_token"],
        csv_text=valid_csv(),
    )
    admin_preview = preview_csv(
        client,
        token=admin["access_token"],
        csv_text=valid_csv(sale_external_id="sale_admin"),
    )
    sales_response = client.post(
        "/api/v1/imports/csv/preview",
        headers=auth_headers(sales["access_token"]),
        files={"file": ("import.csv", valid_csv().encode("utf-8"), "text/csv")},
    )
    unauthenticated = client.post(
        "/api/v1/imports/csv/preview",
        files={"file": ("import.csv", valid_csv().encode("utf-8"), "text/csv")},
    )

    assert owner_preview["valid_rows"] == 1
    assert admin_preview["valid_rows"] == 1
    assert sales_response.status_code == 403
    assert unauthenticated.status_code == 401


def test_preview_validation_and_no_business_records_created(
    client: TestClient,
) -> None:
    owner = register_company(client)
    csv_text = (
        "customer_external_id,customer_name,sale_date,amount,currency,"
        "sale_external_id,document_kind,payment_status,document_status\n"
        "cust_1,Valid Customer,2026-06-15,\"1,000,000\",UZS,sale_1,sale,paid,posted\n"
        "cust_2,Bad Date,not-a-date,100,UZS,sale_2,sale,paid,posted\n"
        "cust_3,Negative,2026-06-15,-1,UZS,sale_3,sale,paid,posted\n"
        "cust_4,Bad Currency,2026-06-15,100,USZZ,sale_4,sale,paid,posted\n"
        "cust_5,Duplicate A,2026-06-15,100,UZS,dup_1,sale,paid,posted\n"
        "cust_6,Duplicate B,2026-06-15,100,UZS,dup_1,sale,paid,posted\n"
        "cust_7,Refund,2026-06-15,100,UZS,refund_1,refund,paid,posted\n"
    )

    preview = preview_csv(client, token=owner["access_token"], csv_text=csv_text)
    rows_response = client.get(
        f"/api/v1/imports/{preview['import_batch_id']}/rows",
        headers=auth_headers(owner["access_token"]),
    )
    invalid_rows_response = client.get(
        f"/api/v1/imports/{preview['import_batch_id']}/rows?status=invalid",
        headers=auth_headers(owner["access_token"]),
    )
    customers_response = client.get(
        "/api/v1/customers",
        headers=auth_headers(owner["access_token"]),
    )
    sales_response = client.get(
        "/api/v1/sale-records",
        headers=auth_headers(owner["access_token"]),
    )

    assert preview["total_rows"] == 7
    assert preview["valid_rows"] == 2
    assert preview["invalid_rows"] == 5
    assert len(preview["errors"]) == 5
    rows = rows_response.json()["items"]
    refund_row = next(row for row in rows if row["sale_external_id"] == "refund_1")
    sale_row = next(row for row in rows if row["sale_external_id"] == "sale_1")
    assert refund_row["normalized_row_json"]["amount_sign"] == -1
    assert sale_row["normalized_row_json"]["amount_sign"] == 1
    assert invalid_rows_response.json()["pagination"]["total"] == 5
    assert customers_response.json()["pagination"]["total"] == 0
    assert sales_response.json()["pagination"]["total"] == 0


def test_preview_missing_required_column_rejected(client: TestClient) -> None:
    owner = register_company(client)

    response = client.post(
        "/api/v1/imports/csv/preview",
        headers=auth_headers(owner["access_token"]),
        files={
            "file": (
                "import.csv",
                b"customer_external_id,customer_name,sale_date,amount\n"
                b"cust_1,Customer,2026-06-15,100\n",
                "text/csv",
            )
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"]["missing_columns"] == ["currency"]


def test_commit_creates_records_and_recalculates_progress(client: TestClient) -> None:
    owner = register_company(client)
    campaign = create_active_campaign(client, token=owner["access_token"])
    preview = preview_csv(client, token=owner["access_token"], csv_text=valid_csv())

    committed = commit_batch(
        client,
        token=owner["access_token"],
        batch_id=preview["import_batch_id"],
    )
    customers_response = client.get(
        "/api/v1/customers?search=CSV Customer",
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

    assert committed["import_batch"]["status"] == "committed"
    assert committed["stats_json"]["created_customers"] == 1
    assert committed["stats_json"]["created_sales"] == 1
    assert committed["stats_json"]["recalculated_progress_count"] == 1
    assert refs_response.json()[0]["provider"] == "csv"
    assert refs_response.json()[0]["external_id"] == "cust_1"
    assert sales_response.json()["items"][0]["source_key"] == "csv:sale_1"
    assert sales_response.json()["items"][0]["gross_amount_minor"] == 30_000_000
    assert "raw_payload_json" not in sales_response.json()["items"][0]
    assert progress_response.status_code == 200
    assert progress_response.json()["total_amount_minor"] == 30_000_000


def test_invalid_rows_not_committed_and_committed_batch_cannot_recommit(
    client: TestClient,
) -> None:
    owner = register_company(client)
    csv_text = (
        "customer_external_id,customer_name,sale_date,amount,currency,sale_external_id\n"
        "cust_1,Valid Customer,2026-06-15,100,UZS,sale_1\n"
        "cust_2,Invalid Customer,bad-date,100,UZS,sale_2\n"
    )
    preview = preview_csv(client, token=owner["access_token"], csv_text=csv_text)

    committed = commit_batch(
        client,
        token=owner["access_token"],
        batch_id=preview["import_batch_id"],
    )
    second_commit = client.post(
        f"/api/v1/imports/{preview['import_batch_id']}/commit",
        headers=auth_headers(owner["access_token"]),
    )
    sales_response = client.get(
        "/api/v1/sale-records",
        headers=auth_headers(owner["access_token"]),
    )
    invalid_rows_response = client.get(
        f"/api/v1/imports/{preview['import_batch_id']}/rows?status=invalid",
        headers=auth_headers(owner["access_token"]),
    )

    assert committed["import_batch"]["committed_rows"] == 1
    assert committed["import_batch"]["skipped_rows"] == 0
    assert second_commit.status_code == 409
    assert sales_response.json()["pagination"]["total"] == 1
    assert invalid_rows_response.json()["pagination"]["total"] == 1


def test_cancel_batch_before_commit_and_cancelled_batch_cannot_commit(
    client: TestClient,
) -> None:
    owner = register_company(client)
    preview = preview_csv(client, token=owner["access_token"], csv_text=valid_csv())

    cancel_response = client.post(
        f"/api/v1/imports/{preview['import_batch_id']}/cancel",
        headers=auth_headers(owner["access_token"]),
    )
    commit_response = client.post(
        f"/api/v1/imports/{preview['import_batch_id']}/commit",
        headers=auth_headers(owner["access_token"]),
    )

    assert cancel_response.status_code == 200
    assert cancel_response.json()["import_batch"]["status"] == "cancelled"
    assert commit_response.status_code == 409


def test_reimport_same_sale_skips_identical_and_updates_changed(
    client: TestClient,
) -> None:
    owner = register_company(client)
    first = preview_csv(client, token=owner["access_token"], csv_text=valid_csv())
    commit_batch(client, token=owner["access_token"], batch_id=first["import_batch_id"])

    identical = preview_csv(client, token=owner["access_token"], csv_text=valid_csv())
    identical_commit = commit_batch(
        client,
        token=owner["access_token"],
        batch_id=identical["import_batch_id"],
    )
    changed = preview_csv(
        client,
        token=owner["access_token"],
        csv_text=valid_csv(amount="50000000"),
    )
    changed_commit = commit_batch(
        client,
        token=owner["access_token"],
        batch_id=changed["import_batch_id"],
    )
    sales_response = client.get(
        "/api/v1/sale-records",
        headers=auth_headers(owner["access_token"]),
    )

    assert identical_commit["stats_json"]["skipped_sales"] == 1
    assert changed_commit["stats_json"]["updated_sales"] == 1
    assert sales_response.json()["pagination"]["total"] == 1
    assert sales_response.json()["items"][0]["gross_amount_minor"] == 50_000_000


def test_external_ref_matching_and_no_auto_merge_by_contact_fields(
    client: TestClient,
) -> None:
    owner = register_company(client)
    first = preview_csv(client, token=owner["access_token"], csv_text=valid_csv())
    commit_batch(client, token=owner["access_token"], batch_id=first["import_batch_id"])

    same_external_ref = preview_csv(
        client,
        token=owner["access_token"],
        csv_text=valid_csv(
            customer_external_id="cust_1",
            sale_external_id="sale_2",
            customer_name="Updated CSV Customer",
        ),
    )
    commit_batch(
        client,
        token=owner["access_token"],
        batch_id=same_external_ref["import_batch_id"],
    )
    different_external_ref = preview_csv(
        client,
        token=owner["access_token"],
        csv_text=valid_csv(
            customer_external_id="cust_2",
            sale_external_id="sale_3",
            customer_name="Updated CSV Customer",
        ),
    )
    commit_batch(
        client,
        token=owner["access_token"],
        batch_id=different_external_ref["import_batch_id"],
    )
    customers_response = client.get(
        "/api/v1/customers",
        headers=auth_headers(owner["access_token"]),
    )

    assert customers_response.json()["pagination"]["total"] == 2
    names = {item["name"] for item in customers_response.json()["items"]}
    assert names == {"Updated CSV Customer"}


def test_import_batch_list_get_rows_and_company_scoping(client: TestClient) -> None:
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
    first = preview_csv(
        client,
        token=company_one["access_token"],
        csv_text=valid_csv(),
    )
    preview_csv(
        client,
        token=company_two["access_token"],
        csv_text=valid_csv(sale_external_id="other-company-sale"),
    )

    list_response = client.get(
        "/api/v1/imports",
        headers=auth_headers(company_one["access_token"]),
    )
    get_response = client.get(
        f"/api/v1/imports/{first['import_batch_id']}",
        headers=auth_headers(company_one["access_token"]),
    )
    rows_response = client.get(
        f"/api/v1/imports/{first['import_batch_id']}/rows?status=valid",
        headers=auth_headers(company_one["access_token"]),
    )
    cross_company = client.get(
        f"/api/v1/imports/{first['import_batch_id']}",
        headers=auth_headers(company_two["access_token"]),
    )

    assert list_response.status_code == 200
    assert list_response.json()["pagination"]["total"] == 1
    assert get_response.status_code == 200
    assert get_response.json()["id"] == first["import_batch_id"]
    assert rows_response.json()["pagination"]["total"] == 1
    assert cross_company.status_code == 404


def test_standard_error_shape_for_unauthenticated_import(client: TestClient) -> None:
    response = client.get("/api/v1/imports")

    assert response.status_code == 401
    assert response.json()["error"]["request_id"]
