import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

import aiosqlite

from . import queries


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
        # Simple lock to serialize critical DB operations like matching.
        self.lock = asyncio.Lock()

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys = ON")
        await self._conn.executescript(queries.CREATE_TABLES)
        await self._ensure_columns()
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    async def _ensure_columns(self) -> None:
        assert self._conn is not None
        async with self._conn.execute("PRAGMA table_info(users)") as cursor:
            rows = await cursor.fetchall()
        columns = {row["name"] for row in rows}
        if "interests" not in columns:
            await self._conn.execute(
                "ALTER TABLE users ADD COLUMN interests TEXT NOT NULL DEFAULT ''"
            )
        if "only_interest" not in columns:
            await self._conn.execute(
                "ALTER TABLE users ADD COLUMN only_interest INTEGER NOT NULL DEFAULT 0"
            )
        if "premium_until" not in columns:
            await self._conn.execute(
                "ALTER TABLE users ADD COLUMN premium_until TEXT NOT NULL DEFAULT ''"
            )

    async def fetchone(self, query: str, params: tuple[Any, ...] = ()) -> Optional[aiosqlite.Row]:
        assert self._conn is not None
        async with self._conn.execute(query, params) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, query: str, params: tuple[Any, ...] = ()) -> list[aiosqlite.Row]:
        assert self._conn is not None
        async with self._conn.execute(query, params) as cursor:
            return await cursor.fetchall()

    async def execute(self, query: str, params: tuple[Any, ...] = ()) -> None:
        assert self._conn is not None
        await self._conn.execute(query, params)
        await self._conn.commit()

    async def create_user_if_missing(self, user_id: int) -> None:
        await self.execute(queries.INSERT_USER, (user_id, self._now(), "idle"))

    async def get_user(self, user_id: int) -> Optional[aiosqlite.Row]:
        return await self.fetchone(queries.SELECT_USER, (user_id,))

    async def set_state(self, user_id: int, state: str) -> None:
        await self.execute(queries.UPDATE_STATE, (state, user_id))

    async def set_banned(self, user_id: int, is_banned: bool) -> None:
        await self.execute(queries.UPDATE_BANNED, (1 if is_banned else 0, user_id))

    async def increment_chats(self, user_id: int) -> None:
        await self.execute(queries.INCREMENT_CHATS, (user_id,))

    async def add_to_queue(self, user_id: int) -> None:
        await self.execute(queries.INSERT_QUEUE, (user_id, self._now()))

    async def remove_from_queue(self, user_id: int) -> None:
        await self.execute(queries.DELETE_QUEUE, (user_id,))

    async def get_queue_candidate(self, exclude_user_id: int) -> Optional[int]:
        row = await self.fetchone(queries.SELECT_QUEUE_CANDIDATE, (exclude_user_id,))
        return int(row["user_id"]) if row else None

    async def get_queue_candidate_by_interest(
        self, exclude_user_id: int, interest: str
    ) -> Optional[int]:
        row = await self.fetchone(
            queries.SELECT_QUEUE_CANDIDATE_INTEREST, (exclude_user_id, interest)
        )
        return int(row["user_id"]) if row else None

    async def get_queue_candidates(self, exclude_user_id: int) -> list[aiosqlite.Row]:
        return await self.fetchall(queries.SELECT_QUEUE_CANDIDATES, (exclude_user_id,))

    async def create_pair(self, user1_id: int, user2_id: int) -> int:
        assert self._conn is not None
        cursor = await self._conn.execute(queries.INSERT_PAIR, (user1_id, user2_id, self._now()))
        await self._conn.commit()
        return int(cursor.lastrowid)

    async def get_active_pair(self, user_id: int) -> Optional[aiosqlite.Row]:
        return await self.fetchone(queries.SELECT_ACTIVE_PAIR, (user_id, user_id))

    async def end_pair(self, pair_id: int) -> None:
        await self.execute(queries.END_PAIR_BY_ID, (self._now(), pair_id))

    async def add_report(self, reporter_id: int, reported_id: int, reason: str) -> None:
        await self.execute(queries.INSERT_REPORT, (reporter_id, reported_id, reason, self._now()))

    async def stats(self) -> dict[str, int]:
        users = await self.fetchone(queries.STATS_USERS)
        active_chats = await self.fetchone(queries.STATS_ACTIVE_CHATS)
        queue = await self.fetchone(queries.STATS_QUEUE)
        reports = await self.fetchone(queries.STATS_REPORTS)
        return {
            "users": int(users["count"]) if users else 0,
            "active_chats": int(active_chats["count"]) if active_chats else 0,
            "queue": int(queue["count"]) if queue else 0,
            "reports": int(reports["count"]) if reports else 0,
        }

    async def get_active_user_ids(self) -> list[int]:
        rows = await self.fetchall(queries.SELECT_ACTIVE_USERS)
        return [int(row["user_id"]) for row in rows]

    async def get_interests(self, user_id: int) -> str:
        row = await self.fetchone(queries.SELECT_INTERESTS, (user_id,))
        return row["interests"] if row else ""

    async def set_interests(self, user_id: int, interests: str) -> None:
        await self.execute(queries.UPDATE_INTERESTS, (interests, user_id))

    async def get_only_interest(self, user_id: int) -> bool:
        row = await self.fetchone(queries.SELECT_ONLY_INTEREST, (user_id,))
        return bool(row["only_interest"]) if row else False

    async def set_only_interest(self, user_id: int, value: bool) -> None:
        await self.execute(queries.UPDATE_ONLY_INTEREST, (1 if value else 0, user_id))

    async def get_premium_until(self, user_id: int) -> str:
        row = await self.fetchone(queries.SELECT_PREMIUM_UNTIL, (user_id,))
        return row["premium_until"] if row else ""

    async def set_premium_until(self, user_id: int, premium_until: str) -> None:
        await self.execute(queries.UPDATE_PREMIUM_UNTIL, (premium_until, user_id))
