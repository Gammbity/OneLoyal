import logging
from enum import StrEnum
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_request_id
from app.core.settings import get_settings

logger = logging.getLogger(__name__)


class ErrorCode(StrEnum):
    INTERNAL_SERVER_ERROR = "internal_server_error"
    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    FORBIDDEN = "forbidden"
    UNAUTHORIZED = "unauthorized"
    BAD_REQUEST = "bad_request"
    HTTP_ERROR = "http_error"


class AppError(Exception):
    """Base application exception returned with the standard API error shape."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(
        self,
        message: str = "Resource not found.",
        *,
        code: str = ErrorCode.NOT_FOUND,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=404,
            details=details,
        )


class ConflictError(AppError):
    def __init__(
        self,
        message: str = "Resource conflict.",
        *,
        code: str = ErrorCode.CONFLICT,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=409,
            details=details,
        )


class ForbiddenError(AppError):
    def __init__(
        self,
        message: str = "Forbidden.",
        *,
        code: str = ErrorCode.FORBIDDEN,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=403,
            details=details,
        )


class UnauthorizedError(AppError):
    def __init__(
        self,
        message: str = "Unauthorized.",
        *,
        code: str = ErrorCode.UNAUTHORIZED,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=401,
            details=details,
        )


class ValidationAppError(AppError):
    def __init__(
        self,
        message: str = "Validation failed.",
        *,
        code: str = ErrorCode.VALIDATION_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=422,
            details=details,
        )


def _request_id_from(request: Request) -> str:
    return getattr(request.state, "request_id", None) or get_request_id()


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    request_id: str,
    details: Any | None = None,
) -> JSONResponse:
    content = {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id,
        }
    }
    return JSONResponse(status_code=status_code, content=jsonable_encoder(content))


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return _error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
        request_id=_request_id_from(request),
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    message = HTTPStatus(exc.status_code).phrase
    code = ErrorCode.HTTP_ERROR
    details: Any = {}

    if isinstance(exc.detail, dict):
        code = str(exc.detail.get("code", code))
        message = str(exc.detail.get("message", message))
        details = exc.detail.get("details", {})
    elif exc.detail:
        message = str(exc.detail)

    return _error_response(
        status_code=exc.status_code,
        code=code,
        message=message,
        details=details,
        request_id=_request_id_from(request),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return _error_response(
        status_code=422,
        code=ErrorCode.VALIDATION_ERROR,
        message="Request validation failed.",
        details={"errors": exc.errors()},
        request_id=_request_id_from(request),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "Unhandled exception",
        extra={"request_id": _request_id_from(request)},
    )

    settings = get_settings()
    details: dict[str, Any] = {}
    if settings.debug:
        details["exception"] = exc.__class__.__name__

    return _error_response(
        status_code=500,
        code=ErrorCode.INTERNAL_SERVER_ERROR,
        message="Internal server error.",
        details=details,
        request_id=_request_id_from(request),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
