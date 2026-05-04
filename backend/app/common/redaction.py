from typing import Any

SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "token",
    "secret",
    "credential",
    "authorization",
    "refresh",
    "access",
    "encrypted_credentials",
    "raw_token",
)

REDACTED_VALUE = "[REDACTED]"


def redact_sensitive_data(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _redact_value(key, nested)
            for key, nested in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive_data(item) for item in value]
    return value


def _redact_value(key: Any, value: Any) -> Any:
    if _is_sensitive_key(key):
        return REDACTED_VALUE
    return redact_sensitive_data(value)


def _is_sensitive_key(key: Any) -> bool:
    if key is None:
        return False
    key_text = str(key).lower()
    return any(fragment in key_text for fragment in SENSITIVE_KEY_FRAGMENTS)
