from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import AppError, register_exception_handlers
from app.core.middleware import RequestIDMiddleware


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "OneLoyal API"
    assert data["version"] == "0.1.0"
    assert data["environment"] == "local"
    assert "checks" in data


def test_db_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/health/db")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_redis_health_endpoint(client: TestClient) -> None:
    with patch("app.api.v1.health.get_redis_client") as mock_get_redis:
        mock_client = MagicMock()
        mock_client.ping = MagicMock() # Should be async if used with await
        
        async def mock_ping():
            return True
        
        mock_client.ping = mock_ping
        mock_get_redis.return_value = mock_client
        
        response = client.get("/api/v1/health/redis")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_celery_health_endpoint(client: TestClient) -> None:
    with patch("app.workers.celery_app.celery_app.connection_for_read") as mock_conn:
        mock_c = MagicMock()
        mock_c.__enter__.return_value = MagicMock()
        mock_conn.return_value = mock_c
        
        response = client.get("/api/v1/health/celery")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_full_health_endpoint(client: TestClient) -> None:
    with patch("app.api.v1.health.get_redis_client") as mock_get_redis, \
         patch("app.workers.celery_app.celery_app.connection_for_read") as mock_conn:
        
        mock_client = MagicMock()
        async def mock_ping():
            return True
        mock_client.ping = mock_ping
        mock_get_redis.return_value = mock_client
        
        mock_c = MagicMock()
        mock_c.__enter__.return_value = MagicMock()
        mock_conn.return_value = mock_c
        
        response = client.get("/api/v1/health/full")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["checks"]["database"] == "ok"
        assert data["checks"]["redis"] == "ok"
        assert data["checks"]["celery_broker"] == "ok"


def test_request_id_header_exists(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "test-request-id"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-id"


def test_app_error_response_shape() -> None:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise AppError(
            code="example_error",
            message="Example error.",
            status_code=400,
            details={"field": "value"},
        )

    with TestClient(app) as client:
        response = client.get("/boom", headers={"X-Request-ID": "error-request-id"})

    assert response.status_code == 400
    assert response.headers["X-Request-ID"] == "error-request-id"
    assert response.json() == {
        "error": {
            "code": "example_error",
            "message": "Example error.",
            "details": {"field": "value"},
            "request_id": "error-request-id",
        }
    }
