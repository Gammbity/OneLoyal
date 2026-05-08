import uuid
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.datetime import utc_now
from app.modules.sync.models import SyncRun, SyncRunStatus
from app.modules.notifications.models import NotificationEvent, NotificationEventStatus
from app.modules.events.models import DomainEvent, DomainEventStatus


def register_company(
    client: TestClient,
    *,
    slug: str = "ops-company",
    owner_email: str = "ops-owner@example.com",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/register-company",
        json={
            "company_name": "Ops Company",
            "company_slug": slug,
            "owner_full_name": "Ops Owner",
            "owner_email": owner_email,
            "owner_password": "super-secret-password",
        },
    )
    assert response.status_code == 201
    return response.json()


def login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "super-secret-password"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def company_data(client: TestClient) -> dict[str, Any]:
    return register_company(client)


@pytest.fixture
def token(client: TestClient, company_data) -> str:
    return login(client, "ops-owner@example.com")


@pytest.mark.asyncio
async def test_ops_status_endpoint(client: TestClient, token) -> None:
    headers = auth_headers(token)
    response = client.get("/api/v1/ops/status", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "sync_runs" in data
    assert "pending_notification_events_count" in data
    assert "pending_domain_events_count" in data


@pytest.mark.asyncio
async def test_recover_stuck_syncs(client: TestClient, token, db_session: AsyncSession) -> None:
    headers = auth_headers(token)
    now = utc_now()
    
    # 1. Get company_id from token or by querying
    # We can just use the DB to create some stuck runs for the company
    result = await db_session.execute(select(SyncRun).limit(1))
    # Wait, I need to make sure there's an integration to link to.
    # Actually, registration creates a default company.
    
    # Let's just use the API to create something and then mess it up in DB
    # Or just use the DB directly since we have db_session
    
    # Create integration first if none exists (usually none after fresh reg in tests)
    # Actually, let's keep it simple and just use the DB to insert.
    
    # But wait, SyncRun needs an integration_id.
    # Let's find any integration in the DB.
    from app.modules.integrations.models import Integration
    res = await db_session.execute(select(Integration).limit(1))
    integration = res.scalar_one_or_none()
    if not integration:
        # Create one
        from app.modules.companies.models import Company
        res_c = await db_session.execute(select(Company).limit(1))
        company = res_c.scalar_one()
        integration = Integration(
            company_id=company.id,
            name="Test Int",
            provider_type="fake",
            is_active=True,
        )
        db_session.add(integration)
        await db_session.commit()

    company_id = integration.company_id

    # Create one stuck QUEUED
    stuck_queued = SyncRun(
        company_id=company_id,
        integration_id=integration.id,
        sync_type="manual",
        status=SyncRunStatus.QUEUED.value,
        created_at=now - timedelta(minutes=30),
    )
    
    # Create one recent QUEUED
    recent_queued = SyncRun(
        company_id=company_id,
        integration_id=integration.id,
        sync_type="manual",
        status=SyncRunStatus.QUEUED.value,
        created_at=now - timedelta(minutes=1),
    )

    # Create one stuck RUNNING
    stuck_running = SyncRun(
        company_id=company_id,
        integration_id=integration.id,
        sync_type="manual",
        status=SyncRunStatus.RUNNING.value,
        created_at=now - timedelta(minutes=90),
        started_at=now - timedelta(minutes=90),
    )

    db_session.add_all([stuck_queued, recent_queued, stuck_running])
    await db_session.commit()

    # Call recovery
    response = client.post("/api/v1/ops/recover-stuck-syncs", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["recovered_queued_count"] == 1
    assert data["recovered_running_count"] == 1

    # Verify in DB
    await db_session.refresh(stuck_queued)
    await db_session.refresh(recent_queued)
    await db_session.refresh(stuck_running)

    assert stuck_queued.status == SyncRunStatus.FAILED.value
    assert recent_queued.status == SyncRunStatus.QUEUED.value
    assert stuck_running.status == SyncRunStatus.FAILED.value


@pytest.mark.asyncio
async def test_recover_notifications(client: TestClient, token, db_session: AsyncSession) -> None:
    headers = auth_headers(token)
    now = utc_now()

    # We need a company_id
    from app.modules.companies.models import Company
    res_c = await db_session.execute(select(Company).limit(1))
    company = res_c.scalar_one()
    company_id = company.id

    # We also need a domain_event_id for NotificationEvent
    from app.modules.events.models import DomainEvent
    domain_event = DomainEvent(
        company_id=company_id,
        event_type="test",
        aggregate_type="test",
        status=DomainEventStatus.PROCESSED.value,
    )
    db_session.add(domain_event)
    await db_session.commit()

    # Stuck notification (max attempts reached and old)
    stuck_notif = NotificationEvent(
        company_id=company_id,
        domain_event_id=domain_event.id,
        channel="email",
        recipient_type="customer",
        status=NotificationEventStatus.PENDING.value,
        attempts=3,
        created_at=now - timedelta(minutes=120),
    )
    
    # Recent notification
    recent_notif = NotificationEvent(
        company_id=company_id,
        domain_event_id=domain_event.id,
        channel="email",
        recipient_type="customer",
        status=NotificationEventStatus.PENDING.value,
        attempts=0,
        created_at=now - timedelta(minutes=5),
    )

    db_session.add_all([stuck_notif, recent_notif])
    await db_session.commit()

    response = client.post("/api/v1/ops/recover-notifications", headers=headers)
    assert response.status_code == 200
    assert response.json()["failed_count"] == 1

    await db_session.refresh(stuck_notif)
    await db_session.refresh(recent_notif)

    assert stuck_notif.status == NotificationEventStatus.FAILED.value
    assert recent_notif.status == NotificationEventStatus.PENDING.value


def test_ops_rbac(client: TestClient, company_data, token) -> None:
    # 1. Create Sales Manager
    headers = auth_headers(token)
    client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "sm@example.com",
            "full_name": "Sales Manager",
            "password": "super-secret-password",
            "role": "sales_manager",
        },
    )
    sm_token = login(client, "sm@example.com")
    sm_headers = auth_headers(sm_token)

    # 2. Try access ops status -> 403
    response = client.get("/api/v1/ops/status", headers=sm_headers)
    assert response.status_code == 403
