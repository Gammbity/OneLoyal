from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import reset_request_id, set_request_id


class LocaleMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Prefer explicit X-Locale header, fallback to Accept-Language
        lang = request.headers.get("x-locale") or request.headers.get("accept-language") or ""
        if lang:
            # accept-language may contain commas; take first and primary tag
            primary = lang.split(",")[0].strip().split("-")[0]
            primary = primary if primary in ("en", "uz", "ru") else "en"
        else:
            primary = "en"
        request.state.locale = primary
        return await call_next(request)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id

        token = set_request_id(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            reset_request_id(token)

