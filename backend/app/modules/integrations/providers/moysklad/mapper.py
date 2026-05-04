from datetime import datetime
from typing import Any

from app.common.datetime import ensure_timezone_aware
from app.modules.integrations.providers.base import ERPCustomerDTO


def _clean_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _clean_email(value: Any) -> str | None:
    email = _clean_string(value)
    if email is None or "@" not in email:
        return None
    return email.lower()


def _parse_datetime(value: Any) -> datetime | None:
    raw = _clean_string(value)
    if raw is None:
        return None
    try:
        return ensure_timezone_aware(datetime.fromisoformat(raw.replace(" ", "T")))
    except ValueError:
        return None


def _compact_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = {
        "code": payload.get("code"),
        "external_code": payload.get("externalCode"),
        "archived": payload.get("archived"),
        "tags": payload.get("tags"),
        "company_type": payload.get("companyType"),
        "updated": payload.get("updated"),
    }
    return {key: value for key, value in metadata.items() if value is not None}


def _tax_id(payload: dict[str, Any]) -> str | None:
    return (
        _clean_string(payload.get("inn"))
        or _clean_string(payload.get("mod__requisites__uz.inn"))
        or _clean_string(payload.get("mod__requisites__kz.iin"))
    )


def map_counterparty_to_customer(payload: dict[str, Any]) -> ERPCustomerDTO:
    external_id = _clean_string(payload.get("id"))
    if external_id is None:
        raise ValueError("MoySklad counterparty id is missing.")

    return ERPCustomerDTO.model_validate(
        {
            "external_id": external_id,
            "name": _clean_string(payload.get("name")) or external_id,
            "phone": _clean_string(payload.get("phone")),
            "email": _clean_email(payload.get("email")),
            "tax_id": _tax_id(payload),
            "metadata": _compact_metadata(payload),
            "raw_payload": payload,
            "last_seen_at": _parse_datetime(payload.get("updated")),
        }
    )
