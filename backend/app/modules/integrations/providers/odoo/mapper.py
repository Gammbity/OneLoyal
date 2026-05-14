import hashlib
import json
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from app.common.datetime import ensure_timezone_aware
from app.modules.integrations.providers.base import ERPCustomerDTO, ERPSaleDTO


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


def _many2one_id(value: Any) -> str | None:
    if isinstance(value, list) and value and isinstance(value[0], int) and value[0] > 0:
        return str(value[0])
    if isinstance(value, int) and value > 0:
        return str(value)
    return None


def _payment_status_from_state(state: Any, gross: int, paid: int | None) -> str:
    state_str = _clean_string(state)
    if state_str == "paid":
        return "paid"
    if state_str == "in_payment":
        return "partial"
    if state_str == "not_paid":
        return "unpaid"
    if paid is None:
        return "unknown"
    if gross == 0 and paid == 0:
        return "paid"
    if paid <= 0:
        return "unpaid"
    if paid < gross:
        return "partial"
    if paid == gross:
        return "paid"
    return "overpaid"


def _document_status_from_state(state: Any) -> str:
    state_str = _clean_string(state)
    if state_str == "posted":
        return "posted"
    if state_str == "cancel":
        return "cancelled"
    if state_str == "draft":
        return "draft"
    return "unknown"


def map_partner_to_customer(payload: dict[str, Any]) -> ERPCustomerDTO:
    raw_id = payload.get("id")
    if not isinstance(raw_id, int) or raw_id <= 0:
        raise ValueError("Odoo partner id is missing.")
    external_id = str(raw_id)

    metadata = {
        "ref": payload.get("ref"),
        "is_company": payload.get("is_company"),
        "active": payload.get("active"),
        "country": payload.get("country_id"),
        "lang": payload.get("lang"),
    }
    return ERPCustomerDTO.model_validate(
        {
            "external_id": external_id,
            "name": _clean_string(payload.get("name")) or external_id,
            "phone": _clean_string(payload.get("phone"))
            or _clean_string(payload.get("mobile")),
            "email": _clean_email(payload.get("email")),
            "tax_id": _clean_string(payload.get("vat")),
            "metadata": {k: v for k, v in metadata.items() if v is not None},
            "raw_payload": payload,
            "last_seen_at": _parse_datetime(payload.get("write_date")),
        }
    )


def map_invoice_to_sale(
    payload: dict[str, Any],
    *,
    default_currency: str = "UZS",
    currency_scale: int | None = None,
) -> ERPSaleDTO:
    raw_id = payload.get("id")
    if not isinstance(raw_id, int) or raw_id <= 0:
        raise ValueError("Odoo invoice id is missing.")
    external_id = str(raw_id)

    customer_external_id = _many2one_id(payload.get("partner_id"))
    if customer_external_id is None:
        raise ValueError("Odoo invoice partner reference is missing.")

    document_date = (
        _parse_date(payload.get("invoice_date"))
        or _parse_date(payload.get("date"))
        or _parse_date(payload.get("create_date"))
    )
    if document_date is None:
        raise ValueError("Odoo invoice document date is missing.")

    currency_pair = payload.get("currency_id")
    currency_name = None
    if isinstance(currency_pair, list) and len(currency_pair) >= 2:
        currency_name = _clean_string(currency_pair[1])
    currency = (
        currency_name.upper()
        if currency_name and len(currency_name) == 3 and currency_name.isalpha()
        else default_currency.upper()
    )
    scale = currency_scale if currency_scale is not None else (0 if currency == "UZS" else 2)

    gross = _minor_amount(payload.get("amount_total"), scale=scale)
    if gross is None:
        raise ValueError("Odoo invoice amount is missing or invalid.")
    net = _minor_amount(payload.get("amount_untaxed"), scale=scale)
    vat = _minor_amount(payload.get("amount_tax"), scale=scale)
    residual = _minor_amount(payload.get("amount_residual"), scale=scale)
    paid = max(gross - residual, 0) if residual is not None else None
    debt = residual

    content_hash_payload = {
        "id": external_id,
        "partner": customer_external_id,
        "invoice_date": payload.get("invoice_date"),
        "write_date": payload.get("write_date"),
        "amount_total": payload.get("amount_total"),
        "amount_residual": payload.get("amount_residual"),
        "state": payload.get("state"),
        "payment_state": payload.get("payment_state"),
        "currency": currency,
    }

    move_type = _clean_string(payload.get("move_type")) or "out_invoice"
    amount_sign = -1 if move_type == "out_refund" else 1

    return ERPSaleDTO.model_validate(
        {
            "external_id": external_id,
            "customer_external_id": customer_external_id,
            "document_kind": "refund" if amount_sign == -1 else "sale",
            "document_date": document_date,
            "effective_date": document_date,
            "gross_amount_minor": gross,
            "net_amount_minor": net,
            "vat_amount_minor": vat,
            "paid_amount_minor": paid,
            "debt_amount_minor": debt,
            "amount_sign": amount_sign,
            "currency": currency,
            "currency_scale": scale,
            "payment_status": _payment_status_from_state(
                payload.get("payment_state"), gross, paid
            ),
            "document_status": _document_status_from_state(payload.get("state")),
            "erp_document_type": move_type,
            "external_document_number": _clean_string(payload.get("name")),
            "external_updated_at": _parse_datetime(payload.get("write_date")),
            "is_deleted_in_source": False,
            "is_archived_in_source": payload.get("active") is False,
            "raw_payload": payload,
            "content_hash": _stable_content_hash(content_hash_payload),
        }
    )
