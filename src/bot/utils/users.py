from datetime import datetime, timezone
from typing import Optional

from ...db.database import Database


async def ensure_user(db: Database, user_id: int) -> None:
    # Create user record if missing.
    await db.create_user_if_missing(user_id)


async def is_banned(db: Database, user_id: int) -> bool:
    user = await db.get_user(user_id)
    if not user:
        return False
    if bool(user["is_banned"]):
        return True
    return _is_active_until(user["banned_until"] or "")


async def is_muted(db: Database, user_id: int) -> bool:
    user = await db.get_user(user_id)
    if not user:
        return False
    return _is_active_until(user["muted_until"] or "")


async def get_active_restrictions(db: Database, user_id: int) -> tuple[str, str]:
    user = await db.get_user(user_id)
    if not user:
        return "", ""

    banned_until = user["banned_until"] or ""
    muted_until = user["muted_until"] or ""
    if not _is_active_until(banned_until):
        banned_until = ""
    if not _is_active_until(muted_until):
        muted_until = ""
    return banned_until, muted_until


async def get_state(db: Database, user_id: int) -> Optional[str]:
    user = await db.get_user(user_id)
    return user["state"] if user else None


def format_until_text(value: str) -> str:
    dt = _parse_iso(value)
    if not dt:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


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
