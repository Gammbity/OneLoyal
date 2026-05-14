import hashlib
import json
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from app.common.datetime import ensure_timezone_aware
from app.modules.integrations.providers.base import ERPCustomerDTO, ERPSaleDTO

# Default 1C OData attribute names used by standard Russian configurations
# (Управление торговлей, ERP, Бухгалтерия). All can be overridden via
# integration settings field_map to support English/custom configurations.
DEFAULT_CUSTOMER_FIELDS: dict[str, str] = {
    "ref_key": "Ref_Key",
    "name": "Description",
    "code": "Code",
    "tax_id": "ИНН",
    "deletion_mark": "DeletionMark",
    "phone": "Телефон",
    "email": "Email",
    "updated_at": "DataVersion",
}

DEFAULT_SALE_FIELDS: dict[str, str] = {
    "ref_key": "Ref_Key",
    "number": "Number",
    "date": "Date",
    "posted": "Posted",
    "deletion_mark": "DeletionMark",
    "customer_ref": "Контрагент_Key",
    "amount": "СуммаДокумента",
    "vat_amount": "СуммаНДС",
    "currency_code": "ВалютаДокумента_Key",
    "operation_kind": "ВидОперации",
}


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


def _minor_amount(value: Any, *, scale: int) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value)) * (Decimal(10) ** scale)
        amount = amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None
    if amount < 0:
        return None
    return int(amount)


def _stable_content_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _resolve(payload: dict[str, Any], aliases: dict[str, str], key: str) -> Any:
    return payload.get(aliases.get(key, key))


def _merge_field_map(
    default: dict[str, str], override: dict[str, Any] | None
) -> dict[str, str]:
    aliases = dict(default)
    if isinstance(override, dict):
        for key, value in override.items():
            if isinstance(value, str) and value.strip():
                aliases[key] = value.strip()
    return aliases


def map_counterparty_to_customer(
    payload: dict[str, Any],
    *,
    field_map: dict[str, Any] | None = None,
) -> ERPCustomerDTO:
    aliases = _merge_field_map(DEFAULT_CUSTOMER_FIELDS, field_map)
    external_id = _clean_string(_resolve(payload, aliases, "ref_key"))
    if external_id is None:
        raise ValueError("1C counterparty Ref_Key is missing.")

    metadata = {
        "code": _clean_string(_resolve(payload, aliases, "code")),
        "deletion_mark": _resolve(payload, aliases, "deletion_mark"),
        "data_version": _clean_string(_resolve(payload, aliases, "updated_at")),
    }

    return ERPCustomerDTO.model_validate(
        {
            "external_id": external_id,
            "name": _clean_string(_resolve(payload, aliases, "name")) or external_id,
            "phone": _clean_string(_resolve(payload, aliases, "phone")),
            "email": _clean_email(_resolve(payload, aliases, "email")),
            "tax_id": _clean_string(_resolve(payload, aliases, "tax_id")),
            "metadata": {k: v for k, v in metadata.items() if v is not None},
            "raw_payload": payload,
            "last_seen_at": None,
        }
    )


def map_document_to_sale(
    payload: dict[str, Any],
    *,
    default_currency: str = "UZS",
    currency_scale: int | None = None,
    field_map: dict[str, Any] | None = None,
    erp_document_type: str | None = None,
) -> ERPSaleDTO:
    aliases = _merge_field_map(DEFAULT_SALE_FIELDS, field_map)
    external_id = _clean_string(_resolve(payload, aliases, "ref_key"))
    if external_id is None:
        raise ValueError("1C document Ref_Key is missing.")

    customer_external_id = _clean_string(_resolve(payload, aliases, "customer_ref"))
    if customer_external_id is None:
        raise ValueError("1C document counterparty reference is missing.")

    document_date = _parse_date(_resolve(payload, aliases, "date"))
    if document_date is None:
        raise ValueError("1C document date is missing.")

    currency_raw = _clean_string(_resolve(payload, aliases, "currency_code"))
    if currency_raw and len(currency_raw) == 3 and currency_raw.isalpha():
        currency = currency_raw.upper()
    else:
        currency = default_currency.upper()
    scale = (
        currency_scale if currency_scale is not None else (0 if currency == "UZS" else 2)
    )

    gross = _minor_amount(_resolve(payload, aliases, "amount"), scale=scale)
    if gross is None:
        raise ValueError("1C document amount is missing or invalid.")
    vat = _minor_amount(_resolve(payload, aliases, "vat_amount"), scale=scale)

    posted = bool(_resolve(payload, aliases, "posted"))
    deleted = bool(_resolve(payload, aliases, "deletion_mark"))
    operation_kind = _clean_string(_resolve(payload, aliases, "operation_kind"))

    content_hash_payload = {
        "ref_key": external_id,
        "customer_ref": customer_external_id,
        "date": _resolve(payload, aliases, "date"),
        "amount": _resolve(payload, aliases, "amount"),
        "posted": posted,
        "deletion_mark": deleted,
        "currency": currency,
    }

    return ERPSaleDTO.model_validate(
        {
            "external_id": external_id,
            "customer_external_id": customer_external_id,
            "document_kind": "sale",
            "document_date": document_date,
            "effective_date": document_date,
            "gross_amount_minor": gross,
            "vat_amount_minor": vat,
            "amount_sign": 1,
            "currency": currency,
            "currency_scale": scale,
            "payment_status": "unknown",
            "document_status": "posted" if posted else "draft",
            "erp_document_type": erp_document_type or operation_kind,
            "external_document_number": _clean_string(
                _resolve(payload, aliases, "number")
            ),
            "external_updated_at": None,
            "is_deleted_in_source": deleted,
            "is_archived_in_source": False,
            "raw_payload": payload,
            "content_hash": _stable_content_hash(content_hash_payload),
        }
    )
