from typing import Any

import asyncio

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.modules.users.models import User, UserRole, UserStatus


def register_company(
    client: TestClient,
    *,
    slug: str = "acme",
    owner_email: str = "owner@example.com",
    company_name: str = "Acme LLC",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/register-company",
        json={
            "company_name": company_name,
            "company_slug": slug,
            "owner_full_name": "Owner User",
            "owner_email": owner_email,
            "owner_password": "super-secret-password",
        },
    )
    assert response.status_code == 201, response.json()
    return response.json()


def create_platform_admin(client: TestClient) -> None:
    sessionmaker = client.app.state.test_sessionmaker

    async def _create() -> None:
        async with sessionmaker() as session:
            session.add(
                User(
                    company_id=None,
                    email="platform@example.com",
                    full_name="Platform Admin",
                    password_hash=hash_password("platform-secret-password"),
                    role=UserRole.PLATFORM_ADMIN.value,
                    status=UserStatus.ACTIVE.value,
                )
            )
            await session.commit()

    asyncio.run(_create())


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def assert_no_secret_fields(value: Any) -> None:
    if isinstance(value, dict):
        assert "password_hash" not in value
        assert "refresh_token_hash" not in value
        for nested in value.values():
            assert_no_secret_fields(nested)
    elif isinstance(value, list):
        for item in value:
            assert_no_secret_fields(item)


def test_register_company_success(client: TestClient) -> None:
    payload = register_company(client)

    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["user"]["email"] == "owner@example.com"
    assert payload["user"]["role"] == "owner"
    assert payload["company"]["slug"] == "acme"
    assert_no_secret_fields(payload)


def test_register_company_without_slug_uses_company_name(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register-company",
        json={
            "company_name": "Dusel",
            "owner_full_name": "Dusel Admin",
            "owner_email": "dusel@example.com",
            "owner_password": "super-secret-password",
        },
    )

    assert response.status_code == 201, response.json()
    payload = response.json()
    assert payload["company"]["slug"] == "dusel"


def test_platform_admin_can_list_companies(client: TestClient) -> None:
    create_platform_admin(client)
    owner = register_company(client, slug="dusel", owner_email="owner@example.com")

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "platform@example.com",
            "password": "platform-secret-password",
        },
    )
    assert login_response.status_code == 200, login_response.json()

    response = client.get(
        "/api/v1/companies",
        headers=auth_headers(login_response.json()["access_token"]),
    )

    assert response.status_code == 200, response.json()
    slugs = {company["slug"] for company in response.json()}
    assert "dusel" in slugs
    assert owner["company"]["slug"] in slugs


def test_duplicate_email_rejected(client: TestClient) -> None:
    register_company(client, slug="acme", owner_email="owner@example.com")

    response = client.post(
        "/api/v1/auth/register-company",
        json={
            "company_name": "Other LLC",
            "company_slug": "other",
            "owner_full_name": "Other Owner",
            "owner_email": "owner@example.com",
            "owner_password": "super-secret-password",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_duplicate_slug_rejected(client: TestClient) -> None:
    register_company(client, slug="acme", owner_email="owner@example.com")

    response = client.post(
        "/api/v1/auth/register-company",
        json={
            "company_name": "Other LLC",
            "company_slug": "ACME",
            "owner_full_name": "Other Owner",
            "owner_email": "other@example.com",
            "owner_password": "super-secret-password",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["details"]["field"] == "company_slug"


def test_login_success(client: TestClient) -> None:
    register_company(client, owner_email="owner@example.com")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "super-secret-password"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["user"]["email"] == "owner@example.com"
    assert_no_secret_fields(payload)


def test_login_wrong_password_rejected(client: TestClient) -> None:
    register_company(client, owner_email="owner@example.com")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_disabled_user_login_rejected(client: TestClient) -> None:
    owner = register_company(client)
    create_response = client.post(
        "/api/v1/users",
        headers=auth_headers(owner["access_token"]),
        json={
            "email": "admin@example.com",
            "full_name": "Admin User",
            "password": "super-secret-password",
            "role": "admin",
        },
    )
    assert create_response.status_code == 201, create_response.json()
    user_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/v1/users/{user_id}",
        headers=auth_headers(owner["access_token"]),
        json={"status": "disabled"},
    )
    assert update_response.status_code == 200, update_response.json()

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "super-secret-password"},
    )
    assert login_response.status_code == 401


def test_refresh_rotates_token(client: TestClient) -> None:
    payload = register_company(client)

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": payload["refresh_token"]},
    )
    assert response.status_code == 200, response.json()
    refreshed = response.json()

    assert refreshed["access_token"]
    assert refreshed["refresh_token"] != payload["refresh_token"]

    old_token_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": payload["refresh_token"]},
    )
    assert old_token_response.status_code == 401


def test_logout_revokes_session(client: TestClient) -> None:
    payload = register_company(client)

    logout_response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": payload["refresh_token"]},
    )
    assert logout_response.status_code == 200
    assert logout_response.json() == {"success": True}

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": payload["refresh_token"]},
    )
    assert refresh_response.status_code == 401


def test_auth_me_works(client: TestClient) -> None:
    payload = register_company(client)

    response = client.get(
        "/api/v1/auth/me",
        headers=auth_headers(payload["access_token"]),
    )

    assert response.status_code == 200
    assert response.json()["role"] == "owner"
    assert response.json()["company"]["slug"] == "acme"


def test_protected_endpoint_without_token_returns_401(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["request_id"]


def test_role_check_rejects_sales_manager(client: TestClient) -> None:
    owner = register_company(client)
    client.post(
        "/api/v1/users",
        headers=auth_headers(owner["access_token"]),
        json={
            "email": "sales@example.com",
            "full_name": "Sales User",
            "password": "super-secret-password",
            "role": "sales_manager",
        },
    )
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "sales@example.com", "password": "super-secret-password"},
    )
    sales_token = login_response.json()["access_token"]

    response = client.get("/api/v1/users", headers=auth_headers(sales_token))

    assert response.status_code == 403


def test_users_list_is_company_scoped(client: TestClient) -> None:
    company_one = register_company(
        client,
        slug="company-one",
        owner_email="one@example.com",
        company_name="Company One",
    )
    register_company(
        client,
        slug="company-two",
        owner_email="two@example.com",
        company_name="Company Two",
    )

    response = client.get(
        "/api/v1/users",
        headers=auth_headers(company_one["access_token"]),
    )

    assert response.status_code == 200
    emails = {item["email"] for item in response.json()["items"]}
    assert "one@example.com" in emails
    assert "two@example.com" not in emails


def test_company_settings_read_and_update(client: TestClient) -> None:
    payload = register_company(client)

    read_response = client.get(
        "/api/v1/companies/me/settings",
        headers=auth_headers(payload["access_token"]),
    )
    assert read_response.status_code == 200
    assert read_response.json()["reward_claim_enabled_default"] is True

    update_response = client.patch(
        "/api/v1/companies/me/settings",
        headers=auth_headers(payload["access_token"]),
        json={
            "fiscal_year_start_month": 4,
            "reward_claim_enabled_default": False,
            "sync_frequency_minutes": 60,
        },
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["fiscal_year_start_month"] == 4
    assert updated["reward_claim_enabled_default"] is False
    assert updated["sync_frequency_minutes"] == 60


def test_password_and_refresh_hashes_never_returned(client: TestClient) -> None:
    payload = register_company(client)

    responses = [
        payload,
        client.get(
            "/api/v1/auth/me",
            headers=auth_headers(payload["access_token"]),
        ).json(),
        client.get(
            "/api/v1/users",
            headers=auth_headers(payload["access_token"]),
        ).json(),
    ]

    for response in responses:
        assert_no_secret_fields(response)

