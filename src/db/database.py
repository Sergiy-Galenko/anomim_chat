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
        await self._ensure_report_columns()
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
        if "banned_until" not in columns:
            await self._conn.execute(
                "ALTER TABLE users ADD COLUMN banned_until TEXT NOT NULL DEFAULT ''"
            )
        if "muted_until" not in columns:
            await self._conn.execute(
                "ALTER TABLE users ADD COLUMN muted_until TEXT NOT NULL DEFAULT ''"
            )
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
        if "trial_used" not in columns:
            await self._conn.execute(
                "ALTER TABLE users ADD COLUMN trial_used INTEGER NOT NULL DEFAULT 0"
            )
        if "skip_until" not in columns:
            await self._conn.execute(
                "ALTER TABLE users ADD COLUMN skip_until TEXT NOT NULL DEFAULT ''"
            )
        if "auto_search" not in columns:
            await self._conn.execute(
                "ALTER TABLE users ADD COLUMN auto_search INTEGER NOT NULL DEFAULT 0"
            )
        if "content_filter" not in columns:
            await self._conn.execute(
                "ALTER TABLE users ADD COLUMN content_filter INTEGER NOT NULL DEFAULT 1"
            )
        if "lang" not in columns:
            await self._conn.execute(
                "ALTER TABLE users ADD COLUMN lang TEXT NOT NULL DEFAULT 'ru'"
            )

    async def _ensure_report_columns(self) -> None:
        assert self._conn is not None
        async with self._conn.execute("PRAGMA table_info(reports)") as cursor:
            rows = await cursor.fetchall()
        columns = {row["name"] for row in rows}
        if "status" not in columns:
            await self._conn.execute(
                "ALTER TABLE reports ADD COLUMN status TEXT NOT NULL DEFAULT 'new'"
            )
        if "resolved_at" not in columns:
            await self._conn.execute("ALTER TABLE reports ADD COLUMN resolved_at TEXT")
        if "resolved_by" not in columns:
            await self._conn.execute("ALTER TABLE reports ADD COLUMN resolved_by INTEGER")

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
        if is_banned:
            await self.execute(queries.UPDATE_BANNED_UNTIL, ("", user_id))

    async def set_banned_until(self, user_id: int, banned_until: str) -> None:
        await self.execute(queries.UPDATE_BANNED_UNTIL, (banned_until, user_id))

    async def get_banned_until(self, user_id: int) -> str:
        row = await self.fetchone(queries.SELECT_BANNED_UNTIL, (user_id,))
        return row["banned_until"] if row else ""

    async def set_muted_until(self, user_id: int, muted_until: str) -> None:
        await self.execute(queries.UPDATE_MUTED_UNTIL, (muted_until, user_id))

    async def get_muted_until(self, user_id: int) -> str:
        row = await self.fetchone(queries.SELECT_MUTED_UNTIL, (user_id,))
        return row["muted_until"] if row else ""

    async def increment_chats(self, user_id: int) -> None:
        await self.execute(queries.INCREMENT_CHATS, (user_id,))

    async def increment_rating(self, user_id: int, value: int) -> None:
        await self.execute(queries.INCREMENT_RATING, (value, user_id))

    async def add_to_queue(self, user_id: int) -> None:
        await self.execute(queries.INSERT_QUEUE, (user_id, self._now()))

    async def remove_from_queue(self, user_id: int) -> None:
        await self.execute(queries.DELETE_QUEUE, (user_id,))

    async def get_queue_size(self) -> int:
        row = await self.fetchone(queries.SELECT_QUEUE_SIZE)
        return int(row["count"]) if row else 0

    async def get_queue_joined_at(self, user_id: int) -> str:
        row = await self.fetchone(queries.SELECT_QUEUE_JOINED_AT, (user_id,))
        return row["joined_at"] if row else ""

    async def get_queue_position(self, user_id: int) -> int:
        joined_at = await self.get_queue_joined_at(user_id)
        if not joined_at:
            return 0
        row = await self.fetchone(queries.SELECT_QUEUE_POSITION, (user_id,))
        return int(row["pos"]) if row else 0

    async def get_queue_candidate(self, exclude_user_id: int) -> Optional[int]:
        row = await self.fetchone(queries.SELECT_QUEUE_CANDIDATE, (exclude_user_id, self._now()))
        return int(row["user_id"]) if row else None

    async def get_queue_candidate_by_interest(
        self, exclude_user_id: int, interest: str
    ) -> Optional[int]:
        row = await self.fetchone(
            queries.SELECT_QUEUE_CANDIDATE_INTEREST, (exclude_user_id, self._now(), interest)
        )
        return int(row["user_id"]) if row else None

    async def get_queue_candidates(self, exclude_user_id: int) -> list[aiosqlite.Row]:
        return await self.fetchall(queries.SELECT_QUEUE_CANDIDATES, (exclude_user_id, self._now()))

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

    async def get_next_report(self) -> Optional[aiosqlite.Row]:
        return await self.fetchone(queries.SELECT_NEXT_REPORT)

    async def get_report_by_id(self, report_id: int) -> Optional[aiosqlite.Row]:
        return await self.fetchone(queries.SELECT_REPORT_BY_ID, (report_id,))

    async def resolve_report(self, report_id: int, status: str, admin_id: int) -> None:
        await self.execute(
            queries.UPDATE_REPORT_STATUS, (status, self._now(), admin_id, report_id)
        )

    async def add_incident(
        self, actor_id: int | None, target_id: int | None, incident_type: str, payload: str
    ) -> None:
        await self.execute(
            queries.INSERT_INCIDENT,
            (actor_id, target_id, incident_type, payload, self._now()),
        )

    async def add_promo_use(self, user_id: int, code: str) -> None:
        await self.execute(queries.INSERT_PROMO_USE, (user_id, code, self._now()))

    async def has_used_promo(self, user_id: int, code: str) -> bool:
        row = await self.fetchone(queries.SELECT_PROMO_USE, (user_id, code))
        return row is not None

    async def set_pending_rating(self, user_id: int, pair_id: int, target_id: int) -> None:
        await self.execute(
            queries.INSERT_PENDING_RATING,
            (user_id, pair_id, target_id, self._now()),
        )

    async def get_pending_rating(self, user_id: int) -> tuple[int, int] | None:
        row = await self.fetchone(queries.SELECT_PENDING_RATING, (user_id,))
        if not row:
            return None
        return int(row["pair_id"]), int(row["target_id"])

    async def clear_pending_rating(self, user_id: int) -> None:
        await self.execute(queries.DELETE_PENDING_RATING, (user_id,))

    async def submit_rating(
        self, rater_id: int, value: int, expected_target_id: int | None = None
    ) -> tuple[bool, int | None]:
        if value not in (-1, 1):
            return False, None

        async with self.lock:
            assert self._conn is not None
            pending = await self.fetchone(queries.SELECT_PENDING_RATING, (rater_id,))
            if not pending:
                return False, None

            pair_id = int(pending["pair_id"])
            target_id = int(pending["target_id"])
            if expected_target_id is not None and target_id != expected_target_id:
                return False, None

            exists = await self.fetchone(queries.SELECT_CHAT_FEEDBACK_EXISTS, (pair_id, rater_id))
            if exists:
                await self.execute(queries.DELETE_PENDING_RATING, (rater_id,))
                return False, target_id

            try:
                await self._conn.execute("BEGIN")
                await self._conn.execute(
                    queries.INSERT_CHAT_FEEDBACK,
                    (pair_id, rater_id, target_id, value, self._now()),
                )
                await self._conn.execute(queries.INCREMENT_RATING, (value, target_id))
                await self._conn.execute(queries.DELETE_PENDING_RATING, (rater_id,))
                await self._conn.commit()
            except Exception:
                await self._conn.rollback()
                raise

            return True, target_id

    async def stats(self) -> dict[str, int]:
        users = await self.fetchone(queries.STATS_USERS)
        active_chats = await self.fetchone(queries.STATS_ACTIVE_CHATS)
        queue = await self.fetchone(queries.STATS_QUEUE)
        reports = await self.fetchone(queries.STATS_REPORTS)
        banned_perm = await self.fetchone(queries.STATS_BANNED)
        banned_temp = await self.fetchone(queries.STATS_TEMP_BANNED, (self._now(),))
        banned = (int(banned_perm["count"]) if banned_perm else 0) + (
            int(banned_temp["count"]) if banned_temp else 0
        )
        return {
            "users": int(users["count"]) if users else 0,
            "active_chats": int(active_chats["count"]) if active_chats else 0,
            "queue": int(queue["count"]) if queue else 0,
            "reports": int(reports["count"]) if reports else 0,
            "banned": banned,
        }

    async def get_active_user_ids(self) -> list[int]:
        rows = await self.fetchall(queries.SELECT_ACTIVE_USERS, (self._now(),))
        return [int(row["user_id"]) for row in rows]

    async def get_partner_history(self, user_id: int) -> set[int]:
        rows = await self.fetchall(queries.SELECT_PARTNER_HISTORY, (user_id, user_id, user_id))
        result: set[int] = set()
        for row in rows:
            partner_id = row["partner_id"]
            if partner_id is not None:
                result.add(int(partner_id))
        return result

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

    async def get_trial_used(self, user_id: int) -> bool:
        row = await self.fetchone(queries.SELECT_TRIAL_USED, (user_id,))
        return bool(row["trial_used"]) if row else False

    async def set_trial_used(self, user_id: int, value: bool) -> None:
        await self.execute(queries.UPDATE_TRIAL_USED, (1 if value else 0, user_id))

    async def get_skip_until(self, user_id: int) -> str:
        row = await self.fetchone(queries.SELECT_SKIP_UNTIL, (user_id,))
        return row["skip_until"] if row else ""

    async def set_skip_until(self, user_id: int, skip_until: str) -> None:
        await self.execute(queries.UPDATE_SKIP_UNTIL, (skip_until, user_id))

    async def get_auto_search(self, user_id: int) -> bool:
        row = await self.fetchone(queries.SELECT_AUTO_SEARCH, (user_id,))
        return bool(row["auto_search"]) if row else False

    async def set_auto_search(self, user_id: int, value: bool) -> None:
        await self.execute(queries.UPDATE_AUTO_SEARCH, (1 if value else 0, user_id))

    async def get_content_filter(self, user_id: int) -> bool:
        row = await self.fetchone(queries.SELECT_CONTENT_FILTER, (user_id,))
        return bool(row["content_filter"]) if row else True

    async def set_content_filter(self, user_id: int, value: bool) -> None:
        await self.execute(queries.UPDATE_CONTENT_FILTER, (1 if value else 0, user_id))

    async def get_lang(self, user_id: int) -> str:
        row = await self.fetchone(queries.SELECT_LANG, (user_id,))
        if not row:
            return "ru"
        value = (row["lang"] or "").strip().lower()
        return value if value in {"ru", "en"} else "ru"

    async def set_lang(self, user_id: int, lang: str) -> None:
        normalized = lang.strip().lower()
        if normalized not in {"ru", "en"}:
            normalized = "ru"
        await self.execute(queries.UPDATE_LANG, (normalized, user_id))

    async def get_all_premium_until(self) -> list[str]:
        rows = await self.fetchall(queries.SELECT_ALL_PREMIUM_UNTIL)
        return [row["premium_until"] for row in rows]
