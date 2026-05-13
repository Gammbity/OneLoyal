from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.modules.integrations.models import Integration, IntegrationStatus
from app.modules.sync.models import SyncRun, SyncRunStatus
from app.modules.sync.tasks import sync_integration_task


@dataclass
class FakeSyncRunResult:
    id: UUID
    status: str


class FakeSession:
    def __init__(self) -> None:
        self.commit_calls = 0

    async def commit(self) -> None:
        self.commit_calls += 1


class FakeSessionContext:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    async def __aenter__(self) -> FakeSession:
        return self.session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


def create_company_owner(client: TestClient, *, slug: str, email: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/register-company",
        json={
            "company_name": f"{slug.title()} LLC",
            "company_slug": slug,
            "owner_full_name": "Owner User",
            "owner_email": email,
            "owner_password": "super-secret-password",
        },
    )
    assert response.status_code == 201, response.json()
    return response.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_fake_integration(client: TestClient, *, token: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/integrations",
        headers=auth_headers(token),
        json={
            "provider": "fake",
            "name": "Fake ERP",
            "settings_json": {
                "customers": [],
                "sales": [],
            },
        },
    )
    assert response.status_code == 201, response.json()
    return response.json()


@pytest.mark.parametrize("fail_on_second", [False, True])
def test_sync_task_cleans_up_worker_resources(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    fail_on_second: bool,
) -> None:
    session = FakeSession()
    cleanup_calls = {"redis": 0, "db": 0}
    call_count = {"value": 0}

    async def fake_execute_sync_run(*args, **kwargs):
        call_count["value"] += 1
        if fail_on_second and call_count["value"] == 2:
            raise RuntimeError("boom")
        return FakeSyncRunResult(id=uuid4(), status="success")

    async def fake_close_redis_client() -> None:
        cleanup_calls["redis"] += 1

    async def fake_dispose_db_engine() -> None:
        cleanup_calls["db"] += 1

    monkeypatch.setattr("app.modules.sync.tasks.AsyncSessionLocal", lambda: FakeSessionContext(session))
    monkeypatch.setattr("app.modules.sync.tasks.sync_service.execute_sync_run", fake_execute_sync_run)
    monkeypatch.setattr("app.workers.async_runtime.close_redis_client", fake_close_redis_client)
    monkeypatch.setattr("app.workers.async_runtime.dispose_db_engine", fake_dispose_db_engine)

    result_one = sync_integration_task(str(uuid4()))
    assert result_one["status"] == "success"
    assert session.commit_calls == 1

    if fail_on_second:
        with pytest.raises(RuntimeError, match="boom"):
            sync_integration_task(str(uuid4()))
    else:
        result_two = sync_integration_task(str(uuid4()))
        assert result_two["status"] == "success"

    assert cleanup_calls["redis"] == 2
    assert cleanup_calls["db"] == 2


def test_recover_stuck_sync_runs_clears_stale_redis_locks(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = create_company_owner(client, slug="sync-recovery", email="owner@sync.example")

    redis_state: dict[str, str] = {}

    class FakeRedis:
        async def delete(self, key: str) -> None:
            redis_state.pop(key, None)

    monkeypatch.setattr("app.modules.ops.service.get_redis_client", lambda: FakeRedis())

    sessionmaker = client.app.state.test_sessionmaker

    async def seed_stuck_running() -> tuple[UUID, UUID]:
        async with sessionmaker() as session:
            company_id = UUID(owner["company"]["id"])
            integration = Integration(
                company_id=company_id,
                provider="fake",
                name="Stuck Integration",
                status=IntegrationStatus.ACTIVE.value,
            )
            session.add(integration)
            await session.flush()

            sync_run = SyncRun(
                company_id=company_id,
                integration_id=integration.id,
                sync_type="manual",
                status=SyncRunStatus.RUNNING.value,
                started_at=sync_run_started_at(),
            )
            session.add(sync_run)
            await session.commit()
            return integration.id, sync_run.id

    def sync_run_started_at():
        from app.common.datetime import utc_now

        return utc_now() - timedelta(minutes=90)

    import asyncio

    integration_id, sync_run_id = asyncio.run(seed_stuck_running())
    redis_state[f"sync:integration:{integration_id}"] = "stale-token"

    recover_response = client.post(
        "/api/v1/ops/recover-stuck-syncs",
        headers=auth_headers(owner["access_token"]),
    )
    assert recover_response.status_code == 200, recover_response.json()
    assert recover_response.json()["recovered_running_count"] == 1
    assert redis_state == {}

    async def verify_recovered() -> str:
        async with sessionmaker() as session:
            result = await session.get(SyncRun, sync_run_id)
            assert result is not None
            return result.status

    assert asyncio.run(verify_recovered()) == SyncRunStatus.FAILED.value