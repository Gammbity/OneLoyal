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
    response = client.get("/api/v1/health/redis")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_celery_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/health/celery")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_full_health_endpoint(client: TestClient) -> None:
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

