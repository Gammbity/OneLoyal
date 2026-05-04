import asyncio
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient

from app.common.redaction import REDACTED_VALUE, SENSITIVE_KEY_FRAGMENTS, redact_sensitive_data
from app.modules.sync.service import sync_service


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
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/campaigns",
        headers=auth_headers(token),
        json={
            "title": title,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
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


def revoke_magic_link(
    client: TestClient,
    *,
    token: str,
    customer_id: str,
    token_id: str,
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/customers/{customer_id}/magic-links/{token_id}/revoke",
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.json()
    return response.json()


def create_portal_session(client: TestClient, *, raw_token: str) -> dict[str, Any]:
    response = client.post("/api/v1/portal/session", json={"token": raw_token})
    assert response.status_code == 200, response.json()
    return response.json()


def list_audit_logs(
    client: TestClient,
    *,
    token: str,
    **params: Any,
) -> dict[str, Any]:
    response = client.get(
        "/api/v1/audit-logs",
        headers=auth_headers(token),
        params=params,
    )
    assert response.status_code == 200, response.json()
    return response.json()


def list_domain_events(
    client: TestClient,
    *,
    token: str,
    **params: Any,
) -> dict[str, Any]:
    response = client.get(
        "/api/v1/domain-events",
        headers=auth_headers(token),
        params=params,
    )
    assert response.status_code == 200, response.json()
    return response.json()


def assert_sensitive_fields_redacted(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key).lower()
            if any(fragment in key_text for fragment in SENSITIVE_KEY_FRAGMENTS):
                assert nested == REDACTED_VALUE
            else:
                assert_sensitive_fields_redacted(nested)
    elif isinstance(value, list):
        for item in value:
            assert_sensitive_fields_redacted(item)


def test_campaign_audit_logs_created_and_activated(client: TestClient) -> None:
    owner = register_company(client, slug="audit-campaign")
    campaign = create_campaign(client, token=owner["access_token"], title="Audit")
    create_tier(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        title="Tier",
        amount=10_000_000,
    )
    activate_campaign(client, token=owner["access_token"], campaign_id=campaign["id"])

    created_logs = list_audit_logs(
        client,
        token=owner["access_token"],
        action="campaign.created",
    )
    activated_logs = list_audit_logs(
        client,
        token=owner["access_token"],
        action="campaign.activated",
    )

    assert any(
        item["entity_id"] == campaign["id"] for item in created_logs["items"]
    )
    assert any(
        item["entity_id"] == campaign["id"] for item in activated_logs["items"]
    )


def test_magic_link_audit_log_redacts_tokens(client: TestClient) -> None:
    owner = register_company(client, slug="audit-links")
    customer = create_customer(client, token=owner["access_token"])
    magic_link = create_magic_link(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
    )
    created_logs = list_audit_logs(
        client,
        token=owner["access_token"],
        action="magic_link.created",
    )
    created_log = next(
        log
        for log in created_logs["items"]
        if log["entity_id"] == magic_link["token_id"]
    )

    assert "raw_token" not in created_log["after_json"]
    assert "token_hash" not in created_log["after_json"]
    assert "portal_url" not in created_log["after_json"]

    revoke_magic_link(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        token_id=magic_link["token_id"],
    )
    revoked_logs = list_audit_logs(
        client,
        token=owner["access_token"],
        action="magic_link.revoked",
    )
    revoked_log = next(
        log
        for log in revoked_logs["items"]
        if log["entity_id"] == magic_link["token_id"]
    )
    assert "raw_token" not in revoked_log["after_json"]
    assert "token_hash" not in revoked_log["after_json"]


def test_reward_claim_audit_logs_and_events(client: TestClient) -> None:
    owner = register_company(client, slug="audit-claims")
    customer = create_customer(client, token=owner["access_token"])
    campaign = create_campaign(client, token=owner["access_token"], title="Claims")
    tiers = [
        create_tier(
            client,
            token=owner["access_token"],
            campaign_id=campaign["id"],
            title="Tier 1",
            amount=10_000_000,
        ),
        create_tier(
            client,
            token=owner["access_token"],
            campaign_id=campaign["id"],
            title="Tier 2",
            amount=30_000_000,
        ),
    ]
    activate_campaign(client, token=owner["access_token"], campaign_id=campaign["id"])
    create_sale(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        source_key="claim-sale-1",
        amount=35_000_000,
    )
    recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
    )

    claim_response = client.post(
        "/api/v1/reward-claims",
        headers=auth_headers(owner["access_token"]),
        json={
            "campaign_id": campaign["id"],
            "customer_id": customer["id"],
            "gift_tier_id": tiers[1]["id"],
        },
    )
    assert claim_response.status_code == 201, claim_response.json()
    claim = claim_response.json()

    approve = client.post(
        f"/api/v1/reward-claims/{claim['id']}/approve",
        headers=auth_headers(owner["access_token"]),
        json={},
    )
    assert approve.status_code == 200, approve.json()
    fulfill = client.post(
        f"/api/v1/reward-claims/{claim['id']}/fulfill",
        headers=auth_headers(owner["access_token"]),
        json={},
    )
    assert fulfill.status_code == 200, fulfill.json()

    claim_response = client.post(
        "/api/v1/reward-claims",
        headers=auth_headers(owner["access_token"]),
        json={
            "campaign_id": campaign["id"],
            "customer_id": customer["id"],
            "gift_tier_id": tiers[1]["id"],
        },
    )
    assert claim_response.status_code == 201, claim_response.json()
    second_claim = claim_response.json()
    reject = client.post(
        f"/api/v1/reward-claims/{second_claim['id']}/reject",
        headers=auth_headers(owner["access_token"]),
        json={},
    )
    assert reject.status_code == 200, reject.json()

    for action in [
        "reward_claim.created",
        "reward_claim.approved",
        "reward_claim.fulfilled",
        "reward_claim.rejected",
    ]:
        logs = list_audit_logs(client, token=owner["access_token"], action=action)
        assert logs["pagination"]["total"] > 0

    for event_type in [
        "reward_claim_created",
        "reward_claim_approved",
        "reward_claim_fulfilled",
        "reward_claim_rejected",
    ]:
        events = list_domain_events(
            client,
            token=owner["access_token"],
            event_type=event_type,
        )
        assert events["pagination"]["total"] > 0


def test_import_commit_audit_and_event(client: TestClient) -> None:
    owner = register_company(client, slug="audit-import")
    campaign = create_campaign(client, token=owner["access_token"], title="CSV")
    create_tier(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        title="Tier",
        amount=10_000_000,
    )
    activate_campaign(client, token=owner["access_token"], campaign_id=campaign["id"])
    preview = client.post(
        "/api/v1/imports/csv/preview",
        headers=auth_headers(owner["access_token"]),
        files={
            "file": (
                "import.csv",
                b"customer_external_id,customer_name,sale_date,amount,currency,"
                b"sale_external_id,document_number,document_kind,payment_status,"
                b"document_status\n"
                b"cust_1,CSV Customer,2026-06-15,30000000,UZS,"
                b"sale_1,INV-1,sale,paid,posted\n",
                "text/csv",
            )
        },
    )
    assert preview.status_code == 201, preview.json()
    preview_payload = preview.json()

    commit = client.post(
        f"/api/v1/imports/{preview_payload['import_batch_id']}/commit",
        headers=auth_headers(owner["access_token"]),
    )
    assert commit.status_code == 200, commit.json()

    logs = list_audit_logs(
        client,
        token=owner["access_token"],
        action="import.committed",
    )
    assert logs["pagination"]["total"] > 0

    events = list_domain_events(
        client,
        token=owner["access_token"],
        event_type="import_committed",
    )
    assert events["pagination"]["total"] > 0


def test_company_settings_update_audit_log(client: TestClient) -> None:
    owner = register_company(client, slug="audit-settings")
    response = client.patch(
        "/api/v1/companies/me/settings",
        headers=auth_headers(owner["access_token"]),
        json={"sync_frequency_minutes": 30},
    )
    assert response.status_code == 200, response.json()

    logs = list_audit_logs(
        client,
        token=owner["access_token"],
        action="company_settings.updated",
    )
    assert logs["pagination"]["total"] == 1


def test_progress_domain_events_tier_changes_and_no_duplicates(
    client: TestClient,
) -> None:
    owner = register_company(client, slug="progress-events")
    customer = create_customer(client, token=owner["access_token"])
    campaign = create_campaign(client, token=owner["access_token"], title="Progress")
    create_tier(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        title="Tier 1",
        amount=10_000_000,
    )
    create_tier(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        title="Tier 2",
        amount=20_000_000,
    )
    activate_campaign(client, token=owner["access_token"], campaign_id=campaign["id"])

    create_sale(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        source_key="progress-sale-1",
        amount=12_000_000,
    )
    recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
    )

    reached = list_domain_events(
        client,
        token=owner["access_token"],
        event_type="reward_tier_reached",
        campaign_id=campaign["id"],
    )
    recalculated = list_domain_events(
        client,
        token=owner["access_token"],
        event_type="customer_progress_recalculated",
        campaign_id=campaign["id"],
    )
    assert reached["pagination"]["total"] == 1
    assert recalculated["pagination"]["total"] == 1

    create_sale(
        client,
        token=owner["access_token"],
        customer_id=customer["id"],
        source_key="progress-sale-2",
        amount=12_000_000,
    )
    recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
    )

    changed = list_domain_events(
        client,
        token=owner["access_token"],
        event_type="reward_tier_changed",
        campaign_id=campaign["id"],
    )
    assert changed["pagination"]["total"] == 1

    recalc_customer(
        client,
        token=owner["access_token"],
        campaign_id=campaign["id"],
        customer_id=customer["id"],
    )

    reached_again = list_domain_events(
        client,
        token=owner["access_token"],
        event_type="reward_tier_reached",
        campaign_id=campaign["id"],
    )
    changed_again = list_domain_events(
        client,
        token=owner["access_token"],
        event_type="reward_tier_changed",
        campaign_id=campaign["id"],
    )
    recalculated_again = list_domain_events(
        client,
        token=owner["access_token"],
        event_type="customer_progress_recalculated",
        campaign_id=campaign["id"],
    )

    assert reached_again["pagination"]["total"] == 1
    assert changed_again["pagination"]["total"] == 1
    assert recalculated_again["pagination"]["total"] == 2


def test_sync_domain_events_success_and_failure(client: TestClient) -> None:
    owner = register_company(client, slug="sync-events")
    integration_response = client.post(
        "/api/v1/integrations",
        headers=auth_headers(owner["access_token"]),
        json={
            "provider": "fake",
            "name": "Fake ERP",
            "settings_json": {
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
                        "external_id": "sale_1",
                        "customer_external_id": "cust_1",
                        "document_kind": "sale",
                        "document_date": "2026-06-15",
                        "effective_date": "2026-06-15",
                        "gross_amount_minor": 30_000_000,
                        "currency": "UZS",
                        "payment_status": "paid",
                        "document_status": "posted",
                        "external_document_number": "INV-1",
                    }
                ],
            },
        },
    )
    assert integration_response.status_code == 201, integration_response.json()
    integration = integration_response.json()

    sync_response = client.post(
        f"/api/v1/integrations/{integration['id']}/sync",
        headers=auth_headers(owner["access_token"]),
    )
    assert sync_response.status_code == 200, sync_response.json()
    queued = sync_response.json()
    SessionLocal = client.app.state.test_sessionmaker

    async def run_sync() -> None:
        async with SessionLocal() as session:
            await sync_service.execute_sync_run(
                session,
                sync_run_id=UUID(queued["sync_run_id"]),
                use_redis_lock=False,
            )
            await session.commit()

    asyncio.run(run_sync())

    completed = list_domain_events(
        client,
        token=owner["access_token"],
        event_type="sync_completed",
    )
    assert completed["pagination"]["total"] == 1

    failing_integration = client.post(
        "/api/v1/integrations",
        headers=auth_headers(owner["access_token"]),
        json={
            "provider": "fake",
            "name": "Failing ERP",
            "settings_json": {"fail_connection": True},
        },
    )
    assert failing_integration.status_code == 201, failing_integration.json()
    failing = failing_integration.json()

    sync_response = client.post(
        f"/api/v1/integrations/{failing['id']}/sync",
        headers=auth_headers(owner["access_token"]),
    )
    assert sync_response.status_code == 200, sync_response.json()
    queued_fail = sync_response.json()

    async def run_sync_fail() -> None:
        async with SessionLocal() as session:
            await sync_service.execute_sync_run(
                session,
                sync_run_id=UUID(queued_fail["sync_run_id"]),
                use_redis_lock=False,
            )
            await session.commit()

    asyncio.run(run_sync_fail())

    failed = list_domain_events(
        client,
        token=owner["access_token"],
        event_type="sync_failed",
    )
    assert failed["pagination"]["total"] == 1


def test_audit_and_event_rbac_scoping_and_portal_token(
    client: TestClient,
) -> None:
    company_one = register_company(client, slug="audit-scope-one")
    company_two = register_company(
        client,
        slug="audit-scope-two",
        owner_email="owner-two@example.com",
    )

    campaign = create_campaign(client, token=company_one["access_token"], title="Scope")
    create_tier(
        client,
        token=company_one["access_token"],
        campaign_id=campaign["id"],
        title="Tier",
        amount=10_000_000,
    )
    activate_campaign(client, token=company_one["access_token"], campaign_id=campaign["id"])
    progress_customer = create_customer(client, token=company_one["access_token"])
    create_sale(
        client,
        token=company_one["access_token"],
        customer_id=progress_customer["id"],
        source_key="scope-sale",
        amount=12_000_000,
    )
    recalc_customer(
        client,
        token=company_one["access_token"],
        campaign_id=campaign["id"],
        customer_id=progress_customer["id"],
    )

    audit_logs = list_audit_logs(
        client,
        token=company_one["access_token"],
    )
    assert audit_logs["pagination"]["total"] > 0

    company_two_logs = list_audit_logs(
        client,
        token=company_two["access_token"],
    )
    assert company_two_logs["pagination"]["total"] == 0

    company_one_events = list_domain_events(
        client,
        token=company_one["access_token"],
    )
    company_two_events = list_domain_events(
        client,
        token=company_two["access_token"],
    )
    assert company_one_events["pagination"]["total"] > 0
    assert company_two_events["pagination"]["total"] == 0

    sales = create_user_and_login(
        client,
        owner_token=company_one["access_token"],
        email="sales@example.com",
        role="sales_manager",
    )
    forbidden_audit = client.get(
        "/api/v1/audit-logs",
        headers=auth_headers(sales["access_token"]),
    )
    forbidden_events = client.get(
        "/api/v1/domain-events",
        headers=auth_headers(sales["access_token"]),
    )
    assert forbidden_audit.status_code == 403
    assert forbidden_events.status_code == 403

    customer = create_customer(client, token=company_one["access_token"])
    magic_link = create_magic_link(
        client,
        token=company_one["access_token"],
        customer_id=customer["id"],
    )
    portal_session = create_portal_session(client, raw_token=magic_link["raw_token"])
    portal_headers = auth_headers(portal_session["portal_access_token"])
    portal_audit = client.get("/api/v1/audit-logs", headers=portal_headers)
    portal_events = client.get("/api/v1/domain-events", headers=portal_headers)

    assert portal_audit.status_code == 401
    assert portal_audit.json()["error"]["request_id"]
    assert portal_events.status_code == 401
    assert portal_events.json()["error"]["request_id"]


def test_redaction_utility_redacts_sensitive_keys() -> None:
    payload = {
        "password": "secret",
        "token": "raw",
        "nested": {"refresh_token": "value"},
        "items": [{"access_key": "value"}, {"safe": "ok"}],
    }
    redacted = redact_sensitive_data(payload)
    assert redacted["password"] == REDACTED_VALUE
    assert redacted["token"] == REDACTED_VALUE
    assert redacted["nested"]["refresh_token"] == REDACTED_VALUE
    assert redacted["items"][0]["access_key"] == REDACTED_VALUE
    assert redacted["items"][1]["safe"] == "ok"
    assert_sensitive_fields_redacted(redacted)
