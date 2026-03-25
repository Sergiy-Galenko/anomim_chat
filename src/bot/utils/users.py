from datetime import datetime, timezone
from typing import Any, Optional

from ...db.database import Database


async def ensure_user(db: Database, user_id: int) -> None:
    # Create user record if missing.
    await db.create_user_if_missing(user_id)


async def get_user_snapshot(db: Database, user_id: int) -> Any:
    return await db.get_user_snapshot(user_id)

def get_lang_from_snapshot(user: Any) -> str:
    if not user:
        return "ru"
    value = (user["lang"] or "").strip().lower()
    return value if value in {"ru", "en", "uk", "de"} else "ru"


def is_banned_from_snapshot(user: Any) -> bool:
    if not user:
        return False
    if bool(user["is_banned"]):
        return True
    return _is_active_until(user["banned_until"] or "")


def is_muted_from_snapshot(user: Any) -> bool:
    if not user:
        return False
    return _is_active_until(user["muted_until"] or "")


def get_active_restrictions_from_snapshot(user: Any) -> tuple[str, str]:
    if not user:
        return "", ""

    banned_until = user["banned_until"] or ""
    muted_until = user["muted_until"] or ""
    if not _is_active_until(banned_until):
        banned_until = ""
    if not _is_active_until(muted_until):
        muted_until = ""
    return banned_until, muted_until


def get_state_from_snapshot(user: Any) -> Optional[str]:
    return user["state"] if user else None


async def is_banned(db: Database, user_id: int, user: Any = None) -> bool:
    snapshot = user or await db.get_user_snapshot(user_id)
    return is_banned_from_snapshot(snapshot)


async def is_muted(db: Database, user_id: int, user: Any = None) -> bool:
    snapshot = user or await db.get_user_snapshot(user_id)
    return is_muted_from_snapshot(snapshot)


async def get_active_restrictions(db: Database, user_id: int, user: Any = None) -> tuple[str, str]:
    snapshot = user or await db.get_user_snapshot(user_id)
    return get_active_restrictions_from_snapshot(snapshot)


async def get_state(db: Database, user_id: int, user: Any = None) -> Optional[str]:
    snapshot = user or await db.get_user_snapshot(user_id)
    return get_state_from_snapshot(snapshot)


def format_until_text(value: str) -> str:
    dt = _parse_iso(value)
    if not dt:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%d.%m.%Y %H:%M UTC")


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _is_active_until(value: str) -> bool:
    dt = _parse_iso(value)
    if not dt:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt > datetime.now(timezone.utc)
