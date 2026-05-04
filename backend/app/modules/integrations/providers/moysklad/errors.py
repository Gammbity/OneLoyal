from typing import Any


class MoySkladError(Exception):
    """Base MoySklad provider error with sanitized details."""


class MoySkladCredentialsError(MoySkladError):
    """Raised when credentials are missing or unsupported."""


class MoySkladAPIError(MoySkladError):
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
