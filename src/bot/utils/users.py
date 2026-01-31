from typing import Optional

from ...db.database import Database


async def ensure_user(db: Database, user_id: int) -> None:
    # Create user record if missing.
    await db.create_user_if_missing(user_id)


async def is_banned(db: Database, user_id: int) -> bool:
    user = await db.get_user(user_id)
    return bool(user and user["is_banned"])


async def get_state(db: Database, user_id: int) -> Optional[str]:
    user = await db.get_user(user_id)
    return user["state"] if user else None
