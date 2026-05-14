from typing import Any


class OneCError(Exception):
    """Base 1C provider error with sanitized details."""


class OneCCredentialsError(OneCError):
    """Raised when credentials are missing or unsupported."""


class OneCAPIError(OneCError):
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
