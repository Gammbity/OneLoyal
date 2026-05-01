from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import AppError, register_exception_handlers
from app.core.middleware import RequestIDMiddleware


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "OneLoyal API",
        "version": "0.1.0",
        "environment": "local",
    }


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

