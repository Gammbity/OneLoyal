import hashlib
import json
import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from app.common.datetime import ensure_timezone_aware
from app.modules.integrations.providers.base import ERPCustomerDTO, ERPSaleDTO

UUID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


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


def _parse_date(value: Any) -> date | None:
    parsed = _parse_datetime(value)
    if parsed is not None:
        return parsed.date()
    raw = _clean_string(value)
    if raw is None:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _minor_amount(value: Any) -> int | None:
    if value is None:
        return None
    try:
        amount = Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None
    if amount < 0:
        return None
    return int(amount)


def _stable_content_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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


def _meta_href(value: Any) -> str | None:
    if isinstance(value, dict):
        meta = value.get("meta")
        if isinstance(meta, dict):
            return _clean_string(meta.get("href"))
        return _clean_string(value.get("href"))
    return None


def extract_uuid_from_meta(value: Any, *, entity_type: str | None = None) -> str | None:
    if isinstance(value, dict):
        direct_id = _clean_string(value.get("id"))
        if direct_id is not None:
            return direct_id
    href = _meta_href(value)
    if href is None:
        return None
    if entity_type is not None and f"/entity/{entity_type}/" not in href:
        return None
    matches = UUID_PATTERN.findall(href)
    if matches:
        return matches[-1]
    return href.rstrip("/").split("/")[-1] or None


def _demand_currency(payload: dict[str, Any], default_currency: str) -> str:
    rate = payload.get("rate")
    currency_payload = rate.get("currency") if isinstance(rate, dict) else None
    if isinstance(currency_payload, dict):
        for key in ("isoCode", "code", "name"):
            candidate = _clean_string(currency_payload.get(key))
            if candidate is not None and len(candidate) == 3 and candidate.isalpha():
                return candidate.upper()
    return default_currency.upper()


def _payment_status(
    *,
    gross_amount_minor: int,
    paid_amount_minor: int | None,
) -> str:
    if paid_amount_minor is None:
        return "unknown"
    if gross_amount_minor == 0 and paid_amount_minor == 0:
        return "paid"
    if paid_amount_minor <= 0:
        return "unpaid"
    if paid_amount_minor < gross_amount_minor:
        return "partial"
    if paid_amount_minor == gross_amount_minor:
        return "paid"
    return "overpaid"


def _document_status(payload: dict[str, Any]) -> str:
    applicable = payload.get("applicable")
    if applicable is False:
        return "cancelled"
    if applicable is True:
        return "posted"
    return "unknown"


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


def map_demand_to_sale(
    payload: dict[str, Any],
    *,
    default_currency: str = "UZS",
) -> ERPSaleDTO:
    external_id = _clean_string(payload.get("id"))
    if external_id is None:
        raise ValueError("MoySklad demand id is missing.")

    customer_external_id = extract_uuid_from_meta(
        payload.get("agent"),
        entity_type="counterparty",
    )
    if customer_external_id is None:
        raise ValueError("MoySklad demand counterparty reference is missing.")

    document_date = _parse_date(payload.get("moment")) or _parse_date(
        payload.get("created")
    )
    if document_date is None:
        raise ValueError("MoySklad demand document date is missing.")

    gross_amount_minor = _minor_amount(payload.get("sum"))
    if gross_amount_minor is None:
        raise ValueError("MoySklad demand sum is missing or invalid.")

    paid_amount_minor = _minor_amount(payload.get("payedSum"))
    if paid_amount_minor is None:
        paid_amount_minor = _minor_amount(payload.get("paidSum"))
    debt_amount_minor = (
        max(gross_amount_minor - paid_amount_minor, 0)
        if paid_amount_minor is not None
        else None
    )
    currency = _demand_currency(payload, default_currency)
    content_hash_payload = {
        "id": external_id,
        "agent": customer_external_id,
        "moment": payload.get("moment"),
        "updated": payload.get("updated"),
        "sum": payload.get("sum"),
        "payedSum": payload.get("payedSum"),
        "paidSum": payload.get("paidSum"),
        "applicable": payload.get("applicable"),
        "name": payload.get("name"),
        "currency": currency,
    }

    return ERPSaleDTO.model_validate(
        {
            "external_id": external_id,
            "customer_external_id": customer_external_id,
            "document_kind": "sale",
            "document_date": document_date,
            "effective_date": document_date,
            "gross_amount_minor": gross_amount_minor,
            "paid_amount_minor": paid_amount_minor,
            "debt_amount_minor": debt_amount_minor,
            "amount_sign": 1,
            "currency": currency,
            "currency_scale": 0 if currency == "UZS" else 2,
            "payment_status": _payment_status(
                gross_amount_minor=gross_amount_minor,
                paid_amount_minor=paid_amount_minor,
            ),
            "document_status": _document_status(payload),
            "erp_document_type": "demand",
            "external_document_number": _clean_string(payload.get("name")),
            "external_updated_at": _parse_datetime(payload.get("updated")),
            "is_deleted_in_source": payload.get("deleted") is not None,
            "is_archived_in_source": bool(payload.get("archived", False)),
            "raw_payload": payload,
            "content_hash": _stable_content_hash(content_hash_payload),
        }
    )
