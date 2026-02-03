from datetime import datetime, timedelta, timezone


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def is_premium_until(value: str) -> bool:
    dt = _parse_iso(value)
    if not dt:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt > datetime.now(timezone.utc)


def format_premium_until(value: str) -> str:
    dt = _parse_iso(value)
    if not dt:
        return "—"
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def add_premium_days(current_until: str, days: int) -> str:
    now = datetime.now(timezone.utc)
    if days <= 0:
        return current_until
    dt = _parse_iso(current_until)
    if dt:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        base = dt if dt > now else now
    else:
        base = now
    return (base + timedelta(days=days)).isoformat()
