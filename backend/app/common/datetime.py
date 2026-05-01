from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_timezone_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=UTC)
    return value


def to_utc(value: datetime) -> datetime:
    return ensure_timezone_aware(value).astimezone(UTC)


def format_iso(value: datetime) -> str:
    return to_utc(value).isoformat()
