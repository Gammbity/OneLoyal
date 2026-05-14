import asyncio
import logging
from collections.abc import Mapping
from typing import Any

import httpx

from app.core.settings import get_settings
from app.modules.integrations.providers.moysklad.errors import (
    MoySkladAPIError,
    MoySkladCredentialsError,
)

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# MoySklad requires this exact Accept header value (including charset)
REQUIRED_ACCEPT_HEADER = "application/json;charset=utf-8"

# Content-Type value to use for JSON request bodies
JSON_CONTENT_TYPE = "application/json"


def _public_error_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    errors = payload.get("errors")
    if isinstance(errors, list):
        sanitized_errors = []
        for error in errors[:5]:
            if isinstance(error, dict):
                sanitized_errors.append(
                    {
                        "code": error.get("code"),
                        "error": error.get("error"),
                        "error_message": error.get("error_message"),
                        "parameter": error.get("parameter"),
                    }
                )
        return {"errors": sanitized_errors}
    return {}


class MoySkladClient:
    def __init__(
        self,
        *,
        credentials: Mapping[str, Any],
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self.credentials = dict(credentials)
        self.base_url = (base_url or settings.moysklad_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.moysklad_timeout_seconds
        self.max_retries = (
            settings.moysklad_max_retries if max_retries is None else max_retries
        )
        self.transport = transport
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "MoySkladClient":
        headers = {
            "Accept": REQUIRED_ACCEPT_HEADER,
            "Accept-Encoding": "gzip",
        }
        auth: httpx.Auth | None = None

        access_token = self.credentials.get("access_token")
        username = self.credentials.get("username")
        password = self.credentials.get("password")
        if isinstance(access_token, str) and access_token.strip():
            headers["Authorization"] = f"Bearer {access_token.strip()}"
        elif (
            isinstance(username, str)
            and username.strip()
            and isinstance(password, str)
            and password
        ):
            auth = httpx.BasicAuth(username.strip(), password)
        else:
            raise MoySkladCredentialsError("MoySklad credentials are missing.")

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            headers=headers,
            auth=auth,
            transport=self.transport,
        )
        return self

    async def post(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any | None = None,
    ) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError(
                "MoySkladClient must be used as an async context manager."
            )

        response: httpx.Response | None = None
        for attempt in range(self.max_retries + 1):
            # Ensure Content-Type is exactly application/json for JSON bodies
            kwargs: dict[str, Any] = {"params": dict(params or {})}
            if json is not None:
                kwargs["json"] = json
                headers = {"Content-Type": JSON_CONTENT_TYPE}
            else:
                headers = {}

            response = await self._client.post(path, headers=headers, **kwargs)
            if (
                response.status_code in RETRYABLE_STATUS_CODES
                and attempt < self.max_retries
            ):
                await asyncio.sleep(self._retry_delay_seconds(response, attempt))
                continue
            break

        if response is None:
            raise MoySkladAPIError(
                status_code=0,
                message="MoySklad request did not produce a response.",
            )
        if response.status_code >= 400:
            raise self._api_error(response)

        try:
            payload = response.json()
        except ValueError as exc:
            raise MoySkladAPIError(
                status_code=response.status_code,
                message="MoySklad returned invalid JSON.",
            ) from exc
        if not isinstance(payload, dict):
            raise MoySkladAPIError(
                status_code=response.status_code,
                message="MoySklad returned an unexpected response shape.",
            )
        return payload

    async def __aexit__(self, *_: object) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def get(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError(
                "MoySkladClient must be used as an async context manager."
            )

        params_dict = dict(params or {})
        logger.debug(
            "MoySklad GET request",
            extra={
                "path": path,
                "params": params_dict,
                "base_url": self.base_url,
            },
        )

        response: httpx.Response | None = None
        for attempt in range(self.max_retries + 1):
            response = await self._client.get(path, params=params_dict)
            if (
                response.status_code in RETRYABLE_STATUS_CODES
                and attempt < self.max_retries
            ):
                logger.debug(
                    "MoySklad GET retry",
                    extra={
                        "status_code": response.status_code,
                        "attempt": attempt,
                    },
                )
                await asyncio.sleep(self._retry_delay_seconds(response, attempt))
                continue
            break

        if response is None:
            raise MoySkladAPIError(
                status_code=0,
                message="MoySklad request did not produce a response.",
            )
        if response.status_code >= 400:
            raise self._api_error(response)

        try:
            payload = response.json()
        except ValueError as exc:
            raise MoySkladAPIError(
                status_code=response.status_code,
                message="MoySklad returned invalid JSON.",
            ) from exc
        if not isinstance(payload, dict):
            raise MoySkladAPIError(
                status_code=response.status_code,
                message="MoySklad returned an unexpected response shape.",
            )

        rows = payload.get("rows")
        row_count = len(rows) if isinstance(rows, list) else 0
        meta = payload.get("meta", {})
        logger.debug(
            "MoySklad GET response",
            extra={
                "status_code": response.status_code,
                "path": path,
                "rows_returned": row_count,
                "meta_size": meta.get("size"),
                "meta_limit": meta.get("limit"),
                "meta_offset": meta.get("offset"),
            },
        )
        return payload

    async def list_counterparties(
        self,
        *,
        offset: int,
        limit: int,
    ) -> dict[str, Any]:
        return await self.get(
            "/entity/counterparty",
            params={"offset": offset, "limit": limit},
        )

    async def list_demands(
        self,
        *,
        offset: int,
        limit: int,
        filters: list[str] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"offset": offset, "limit": limit}
        if filters:
            params["filter"] = ";".join(filters)
        return await self.get("/entity/demand", params=params)

    def _api_error(self, response: httpx.Response) -> MoySkladAPIError:
        details: dict[str, Any] = {
            "status_code": response.status_code,
            "rate_limit_limit": response.headers.get("X-RateLimit-Limit"),
            "rate_limit_remaining": response.headers.get("X-RateLimit-Remaining"),
            "retry_after_ms": response.headers.get("X-Lognex-Retry-After"),
        }
        try:
            details.update(_public_error_payload(response.json()))
        except ValueError:
            pass

        if response.status_code == 401:
            message = "MoySklad authentication failed."
        elif response.status_code == 429:
            message = "MoySklad rate limit exceeded."
        elif response.status_code >= 500:
            message = "MoySklad service error."
        else:
            message = "MoySklad request failed."
        return MoySkladAPIError(
            status_code=response.status_code,
            message=message,
            details={key: value for key, value in details.items() if value is not None},
        )

    def _retry_delay_seconds(self, response: httpx.Response, attempt: int) -> float:
        retry_after_ms = response.headers.get("X-Lognex-Retry-After")
        if retry_after_ms is not None:
            try:
                return min(float(retry_after_ms) / 1000, 10.0)
            except ValueError:
                pass
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return min(float(retry_after), 10.0)
            except ValueError:
                pass
        return min(0.25 * (2**attempt), 5.0)
