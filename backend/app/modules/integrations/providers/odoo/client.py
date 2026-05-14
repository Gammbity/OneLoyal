import asyncio
from collections.abc import Mapping
from typing import Any

import httpx

from app.core.settings import get_settings
from app.modules.integrations.providers.odoo.errors import (
    OdooAPIError,
    OdooCredentialsError,
)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _sanitize_error(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    error = payload.get("error")
    if not isinstance(error, dict):
        return {}
    data = error.get("data") if isinstance(error.get("data"), dict) else {}
    return {
        "code": error.get("code"),
        "message": error.get("message"),
        "name": data.get("name"),
        "arguments": data.get("arguments"),
    }


class OdooClient:
    def __init__(
        self,
        *,
        credentials: Mapping[str, Any],
        base_url: str | None = None,
        database: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self.credentials = dict(credentials)
        configured_url = base_url or self.credentials.get("url")
        if not isinstance(configured_url, str) or not configured_url.strip():
            raise OdooCredentialsError("Odoo base URL is missing.")
        self.base_url = configured_url.strip().rstrip("/")
        self.database = database or self.credentials.get("db") or self.credentials.get(
            "database"
        )
        if not isinstance(self.database, str) or not self.database.strip():
            raise OdooCredentialsError("Odoo database name is missing.")
        self.database = self.database.strip()
        self.timeout_seconds = timeout_seconds or settings.odoo_timeout_seconds
        self.max_retries = (
            settings.odoo_max_retries if max_retries is None else max_retries
        )
        self.transport = transport
        self._client: httpx.AsyncClient | None = None
        self._uid: int | None = None
        self._password: str | None = None
        self._username: str | None = None

    async def __aenter__(self) -> "OdooClient":
        username = self.credentials.get("username")
        password = self.credentials.get("api_key") or self.credentials.get("password")
        if not isinstance(username, str) or not username.strip():
            raise OdooCredentialsError("Odoo username is missing.")
        if not isinstance(password, str) or not password:
            raise OdooCredentialsError("Odoo password or API key is missing.")
        self._username = username.strip()
        self._password = password
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            transport=self.transport,
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def _ensure_uid(self) -> int:
        if self._uid is not None:
            return self._uid
        payload = await self._jsonrpc(
            service="common",
            method="login",
            args=[self.database, self._username, self._password],
        )
        result = payload.get("result")
        if not isinstance(result, int) or result <= 0:
            raise OdooCredentialsError("Odoo authentication failed.")
        self._uid = result
        return result

    async def _jsonrpc(
        self,
        *,
        service: str,
        method: str,
        args: list[Any],
    ) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("OdooClient must be used as an async context manager.")

        body = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {"service": service, "method": method, "args": args},
        }
        response: httpx.Response | None = None
        for attempt in range(self.max_retries + 1):
            response = await self._client.post("/jsonrpc", json=body)
            if (
                response.status_code in RETRYABLE_STATUS_CODES
                and attempt < self.max_retries
            ):
                await asyncio.sleep(self._retry_delay_seconds(response, attempt))
                continue
            break

        if response is None:
            raise OdooAPIError(
                status_code=0,
                message="Odoo request did not produce a response.",
            )
        if response.status_code >= 400:
            raise self._api_error(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise OdooAPIError(
                status_code=response.status_code,
                message="Odoo returned invalid JSON.",
            ) from exc
        if not isinstance(payload, dict):
            raise OdooAPIError(
                status_code=response.status_code,
                message="Odoo returned an unexpected response shape.",
            )
        if "error" in payload:
            details = _sanitize_error(payload)
            raise OdooAPIError(
                status_code=response.status_code,
                message=str(details.get("message") or "Odoo request failed."),
                details={k: v for k, v in details.items() if v is not None},
            )
        return payload

    async def execute_kw(
        self,
        *,
        model: str,
        method: str,
        args: list[Any],
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        uid = await self._ensure_uid()
        payload = await self._jsonrpc(
            service="object",
            method="execute_kw",
            args=[self.database, uid, self._password, model, method, args, kwargs or {}],
        )
        return payload.get("result")

    async def search_read(
        self,
        *,
        model: str,
        domain: list[Any],
        fields: list[str],
        offset: int,
        limit: int,
        order: str | None = None,
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {
            "fields": fields,
            "offset": offset,
            "limit": limit,
        }
        if order:
            kwargs["order"] = order
        result = await self.execute_kw(
            model=model,
            method="search_read",
            args=[domain],
            kwargs=kwargs,
        )
        return list(result) if isinstance(result, list) else []

    def _api_error(self, response: httpx.Response) -> OdooAPIError:
        details: dict[str, Any] = {
            "status_code": response.status_code,
            "retry_after": response.headers.get("Retry-After"),
        }
        try:
            details.update(_sanitize_error(response.json()))
        except ValueError:
            pass
        if response.status_code == 401:
            message = "Odoo authentication failed."
        elif response.status_code == 429:
            message = "Odoo rate limit exceeded."
        elif response.status_code >= 500:
            message = "Odoo service error."
        else:
            message = "Odoo request failed."
        return OdooAPIError(
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
