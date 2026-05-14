from typing import Any


class OdooError(Exception):
    """Base Odoo provider error with sanitized details."""


class OdooCredentialsError(OdooError):
    """Raised when credentials are missing or unsupported."""


class OdooAPIError(OdooError):
    def __init__(
        self,
        *,
        status_code: int,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.details = details or {}
        super().__init__(message)
