import asyncio
from collections.abc import Mapping
from typing import Any

import httpx

from app.core.settings import get_settings
from app.modules.integrations.providers.one_c.errors import (
    OneCAPIError,
    OneCCredentialsError,
)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _sanitize_error(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    error = payload.get("odata.error") or payload.get("error")
    if not isinstance(error, dict):
        return {}
    message = error.get("message")
    if isinstance(message, dict):
        message = message.get("value")
    return {
        "code": error.get("code"),
        "message": message,
    }


class OneCClient:
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
        configured_url = base_url or self.credentials.get("base_url")
        if not isinstance(configured_url, str) or not configured_url.strip():
            raise OneCCredentialsError("1C base URL is missing.")
        self.base_url = configured_url.strip().rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.one_c_timeout_seconds
        self.max_retries = (
            settings.one_c_max_retries if max_retries is None else max_retries
        )
        self.transport = transport
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "OneCClient":
        username = self.credentials.get("username")
        password = self.credentials.get("password")
        if (
            not isinstance(username, str)
            or not username.strip()
            or not isinstance(password, str)
            or not password
        ):
            raise OneCCredentialsError("1C credentials are missing.")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            headers={"Accept": "application/json"},
            auth=httpx.BasicAuth(username.strip(), password),
            transport=self.transport,
        )
        return self

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
            raise RuntimeError("OneCClient must be used as an async context manager.")

        merged: dict[str, Any] = {"$format": "json"}
        if params:
            for key, value in params.items():
                if value is None:
                    continue
                merged[key] = value

        response: httpx.Response | None = None
        for attempt in range(self.max_retries + 1):
            response = await self._client.get(path, params=merged)
            if (
                response.status_code in RETRYABLE_STATUS_CODES
                and attempt < self.max_retries
            ):
                await asyncio.sleep(self._retry_delay_seconds(response, attempt))
                continue
            break

        if response is None:
            raise OneCAPIError(
                status_code=0,
                message="1C request did not produce a response.",
            )
        if response.status_code >= 400:
            raise self._api_error(response)

        try:
            payload = response.json()
        except ValueError as exc:
            raise OneCAPIError(
                status_code=response.status_code,
                message="1C returned invalid JSON.",
            ) from exc
        if not isinstance(payload, dict):
            raise OneCAPIError(
                status_code=response.status_code,
                message="1C returned an unexpected response shape.",
            )
        return payload

    async def list_entity(
        self,
        *,
        entity: str,
        offset: int,
        limit: int,
        filter_expr: str | None = None,
        select: list[str] | None = None,
        order_by: str | None = "Ref_Key",
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"$top": limit, "$skip": offset}
        if filter_expr:
            params["$filter"] = filter_expr
        if select:
            params["$select"] = ",".join(select)
        if order_by:
            params["$orderby"] = order_by
        payload = await self.get(f"/odata/standard.odata/{entity}", params=params)
        rows = payload.get("value")
        return list(rows) if isinstance(rows, list) else []

    def _api_error(self, response: httpx.Response) -> OneCAPIError:
        details: dict[str, Any] = {
            "status_code": response.status_code,
            "retry_after": response.headers.get("Retry-After"),
        }
        try:
            details.update(_sanitize_error(response.json()))
        except ValueError:
            pass
        if response.status_code == 401:
            message = "1C authentication failed."
        elif response.status_code == 429:
            message = "1C rate limit exceeded."
        elif response.status_code >= 500:
            message = "1C service error."
        else:
            message = "1C request failed."
        return OneCAPIError(
            status_code=response.status_code,
            message=message,
            details={k: v for k, v in details.items() if v is not None},
        )

    def _retry_delay_seconds(self, response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return min(float(retry_after), 10.0)
            except ValueError:
                pass
        return min(0.25 * (2**attempt), 5.0)
