import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import monotonic
from typing import Any, Optional

import aiosqlite

from . import queries

DEFAULT_VIRTUAL_COMPANION_IDS = (-101, -102, -103, -104, -105)
DEFAULT_VIRTUAL_QUEUE_THRESHOLD = 4
USER_CONTEXT_TOUCH_INTERVAL_SEC = 30.0
MEDIA_ARCHIVE_CLEANUP_INTERVAL_SEC = 3600.0


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
        # Simple lock to serialize critical DB operations like matching.
        self.lock = asyncio.Lock()
        self._known_users: set[int] = set()
        self._lang_cache: dict[int, str] = {}
        self._user_touch_cache: dict[int, tuple[str, str, str, float]] = {}
        self._media_cleanup_deadlines: dict[int, float] = {}

    def _resolve_db_file(self) -> Optional[Path]:
        if not self.db_path or self.db_path == ":memory:" or self.db_path.startswith("file:"):
            return None
        return Path(self.db_path).expanduser()

    async def connect(self) -> None:
        db_file = self._resolve_db_file()
        if db_file is not None:
            db_file.parent.mkdir(parents=True, exist_ok=True)

        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys = ON")
        await self._conn.execute("PRAGMA busy_timeout = 5000")
        if db_file is not None:
            await self._conn.execute("PRAGMA journal_mode = WAL")
        await self._conn.executescript(queries.CREATE_TABLES)
        await self._ensure_columns()
        await self._ensure_report_columns()
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _days_ago(self, days: int) -> str:
        return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    def _remember_user(self, user_id: int) -> None:
        self._known_users.add(user_id)

    def _prime_user_cache(self, row: aiosqlite.Row) -> None:
        user_id = int(row["user_id"])
        self._remember_user(user_id)
        lang = (row["lang"] or "").strip().lower() if "lang" in row.keys() else ""
        if lang in {"ru", "en"}:
            self._lang_cache[user_id] = lang

    async def _ensure_columns(self) -> None:
        assert self._conn is not None
        async with self._conn.execute("PRAGMA table_info(users)") as cursor:
            rows = await cursor.fetchall()
        columns = {row["name"] for row in rows}
        if "username" not in columns:
            await self._conn.execute(
                "ALTER TABLE users ADD COLUMN username TEXT NOT NULL DEFAULT ''"
            )
        if "first_name" not in columns:
            await self._conn.execute(
                "ALTER TABLE users ADD COLUMN first_name TEXT NOT NULL DEFAULT ''"
            )
        if "last_name" not in columns:
            await self._conn.execute(
                "ALTER TABLE users ADD COLUMN last_name TEXT NOT NULL DEFAULT ''"
            )
        if "last_seen_at" not in columns:
            await self._conn.execute(
                "ALTER TABLE users ADD COLUMN last_seen_at TEXT NOT NULL DEFAULT ''"
            )
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

    async def execute(
        self,
        query: str,
        params: tuple[Any, ...] = (),
        *,
        commit: bool = True,
    ) -> None:
        assert self._conn is not None
        await self._conn.execute(query, params)
        if commit:
            await self._conn.commit()

    async def create_user_if_missing(self, user_id: int) -> None:
        if user_id in self._known_users:
            return
        await self.execute(queries.INSERT_USER, (user_id, self._now(), "idle"))
        self._remember_user(user_id)

    async def get_user(self, user_id: int) -> Optional[aiosqlite.Row]:
        row = await self.fetchone(queries.SELECT_USER, (user_id,))
        if row:
            self._prime_user_cache(row)
        return row

    async def update_user_profile(
        self,
        user_id: int,
        username: str = "",
        first_name: str = "",
        last_name: str = "",
    ) -> None:
        await self.execute(
            queries.UPDATE_USER_PROFILE,
            (
                username.strip(),
                first_name.strip(),
                last_name.strip(),
                self._now(),
                user_id,
            ),
        )
        self._remember_user(user_id)

    async def touch_user_context(
        self,
        user_id: int,
        username: str = "",
        first_name: str = "",
        last_name: str = "",
    ) -> None:
        normalized_username = username.strip()
        normalized_first_name = first_name.strip()
        normalized_last_name = last_name.strip()
        now_monotonic = monotonic()
        cached = self._user_touch_cache.get(user_id)
        if cached is not None:
            cached_username, cached_first_name, cached_last_name, cached_at = cached
            if (
                cached_username == normalized_username
                and cached_first_name == normalized_first_name
                and cached_last_name == normalized_last_name
                and now_monotonic - cached_at < USER_CONTEXT_TOUCH_INTERVAL_SEC
            ):
                self._remember_user(user_id)
                return

        now_iso = self._now()
        await self.execute(
            queries.UPSERT_USER_CONTEXT,
            (
                user_id,
                now_iso,
                normalized_username,
                normalized_first_name,
                normalized_last_name,
                now_iso,
            ),
        )
        self._remember_user(user_id)
        self._user_touch_cache[user_id] = (
            normalized_username,
            normalized_first_name,
            normalized_last_name,
            now_monotonic,
        )

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

    async def queue_user_for_search(self, user_id: int) -> None:
        assert self._conn is not None
        joined_at = self._now()
        try:
            await self._conn.execute("BEGIN")
            await self._conn.execute(queries.UPDATE_STATE, ("searching", user_id))
            await self._conn.execute(queries.INSERT_QUEUE, (user_id, joined_at))
            await self._conn.commit()
        except Exception:
            await self._conn.rollback()
            raise

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

    async def start_virtual_pair(self, user_id: int, companion_id: int) -> int:
        assert self._conn is not None
        try:
            await self._conn.execute("BEGIN")
            await self._conn.execute(queries.DELETE_QUEUE, (user_id,))
            await self._conn.execute(queries.UPDATE_STATE, ("chatting", user_id))
            cursor = await self._conn.execute(
                queries.INSERT_PAIR,
                (user_id, companion_id, self._now()),
            )
            await self._conn.execute(queries.INCREMENT_CHATS, (user_id,))
            await self._conn.commit()
            return int(cursor.lastrowid)
        except Exception:
            await self._conn.rollback()
            raise

    async def start_human_pair(self, user1_id: int, user2_id: int) -> int:
        assert self._conn is not None
        try:
            await self._conn.execute("BEGIN")
            await self._conn.execute(queries.DELETE_QUEUE, (user1_id,))
            await self._conn.execute(queries.DELETE_QUEUE, (user2_id,))
            await self._conn.execute(queries.UPDATE_STATE, ("chatting", user1_id))
            await self._conn.execute(queries.UPDATE_STATE, ("chatting", user2_id))
            cursor = await self._conn.execute(
                queries.INSERT_PAIR,
                (user1_id, user2_id, self._now()),
            )
            await self._conn.execute(queries.INCREMENT_CHATS, (user1_id,))
            await self._conn.execute(queries.INCREMENT_CHATS, (user2_id,))
            await self._conn.commit()
            return int(cursor.lastrowid)
        except Exception:
            await self._conn.rollback()
            raise

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

    async def create_promo_code(
        self,
        code: str,
        days: int,
        usage_limit: int,
        created_by: int | None,
    ) -> None:
        await self.execute(
            queries.INSERT_PROMO_CODE,
            (code.upper(), days, usage_limit, self._now(), created_by),
        )

    async def get_managed_promo_code(self, code: str) -> Optional[aiosqlite.Row]:
        return await self.fetchone(queries.SELECT_PROMO_CODE, (code.upper(),))

    async def get_recent_promo_codes(self, limit: int = 10) -> list[aiosqlite.Row]:
        return await self.fetchall(queries.SELECT_RECENT_PROMO_CODES, (limit,))

    async def get_setting(self, key: str, default: str = "") -> str:
        row = await self.fetchone(queries.SELECT_APP_SETTING, (key,))
        return row["value"] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        await self.execute(queries.UPSERT_APP_SETTING, (key, value))

    async def get_virtual_bot_settings(self) -> dict[str, int | list[int]]:
        default_ids = list(DEFAULT_VIRTUAL_COMPANION_IDS)
        raw_count = await self.get_setting(
            "virtual_bots_enabled_count",
            str(len(default_ids)),
        )
        raw_threshold = await self.get_setting(
            "virtual_bots_queue_threshold",
            str(DEFAULT_VIRTUAL_QUEUE_THRESHOLD),
        )
        raw_ids = await self.get_setting(
            "virtual_bots_active_ids",
            ",".join(str(companion_id) for companion_id in default_ids),
        )

        try:
            enabled_count = int(raw_count)
        except ValueError:
            enabled_count = len(default_ids)
        enabled_count = max(0, min(enabled_count, len(default_ids)))

        try:
            queue_threshold = int(raw_threshold)
        except ValueError:
            queue_threshold = DEFAULT_VIRTUAL_QUEUE_THRESHOLD
        queue_threshold = max(0, queue_threshold)

        active_ids: list[int] = []
        for chunk in raw_ids.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            try:
                companion_id = int(chunk)
            except ValueError:
                continue
            if companion_id in DEFAULT_VIRTUAL_COMPANION_IDS and companion_id not in active_ids:
                active_ids.append(companion_id)

        if not active_ids and raw_ids.strip():
            active_ids = default_ids

        available_ids = active_ids[:enabled_count]
        return {
            "enabled_count": enabled_count,
            "queue_threshold": queue_threshold,
            "active_ids": active_ids,
            "available_ids": available_ids,
        }

    async def set_virtual_bot_enabled_count(self, count: int) -> None:
        normalized = max(0, min(count, len(DEFAULT_VIRTUAL_COMPANION_IDS)))
        await self.set_setting("virtual_bots_enabled_count", str(normalized))

    async def set_virtual_bot_queue_threshold(self, threshold: int) -> None:
        await self.set_setting("virtual_bots_queue_threshold", str(max(0, threshold)))

    async def set_virtual_bot_active_ids(self, companion_ids: list[int]) -> None:
        normalized: list[int] = []
        for companion_id in companion_ids:
            if companion_id in DEFAULT_VIRTUAL_COMPANION_IDS and companion_id not in normalized:
                normalized.append(companion_id)
        await self.set_setting(
            "virtual_bots_active_ids",
            ",".join(str(companion_id) for companion_id in normalized),
        )

    async def redeem_managed_promo_code(
        self,
        user_id: int,
        code: str,
    ) -> tuple[str, int | None]:
        normalized = code.upper()
        async with self.lock:
            promo = await self.fetchone(queries.SELECT_PROMO_CODE, (normalized,))
            if not promo:
                return "invalid", None
            if not bool(promo["is_active"]):
                return "inactive", None
            if await self.has_used_promo(user_id, normalized):
                return "used", None

            usage_limit = int(promo["usage_limit"])
            used_count = int(promo["used_count"])
            if usage_limit > 0 and used_count >= usage_limit:
                return "exhausted", None

            assert self._conn is not None
            try:
                await self._conn.execute("BEGIN")
                await self._conn.execute(
                    queries.INSERT_PROMO_USE,
                    (user_id, normalized, self._now()),
                )
                await self._conn.execute(queries.UPDATE_PROMO_CODE_USAGE, (normalized,))
                await self._conn.commit()
            except Exception:
                await self._conn.rollback()
                raise

            return "ok", int(promo["days"])

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

    async def cleanup_media_archive(self, retention_days: int = 3, *, force: bool = False) -> None:
        deadline = self._media_cleanup_deadlines.get(retention_days, 0.0)
        now_monotonic = monotonic()
        if not force and now_monotonic < deadline:
            return
        await self.execute(queries.DELETE_OLD_MEDIA_ARCHIVE, (self._days_ago(retention_days),))
        self._media_cleanup_deadlines[retention_days] = now_monotonic + MEDIA_ARCHIVE_CLEANUP_INTERVAL_SEC

    async def add_media_record(
        self,
        sender_id: int,
        receiver_id: int,
        media_type: str,
        file_id: str,
        caption: str = "",
        retention_days: int = 3,
    ) -> None:
        assert self._conn is not None
        now_monotonic = monotonic()
        cleanup_due = now_monotonic >= self._media_cleanup_deadlines.get(retention_days, 0.0)
        try:
            await self._conn.execute("BEGIN")
            if cleanup_due:
                await self._conn.execute(
                    queries.DELETE_OLD_MEDIA_ARCHIVE,
                    (self._days_ago(retention_days),),
                )
            await self._conn.execute(
                queries.INSERT_MEDIA_ARCHIVE,
                (sender_id, receiver_id, media_type, file_id, caption, self._now()),
            )
            await self._conn.commit()
        except Exception:
            await self._conn.rollback()
            raise
        if cleanup_due:
            self._media_cleanup_deadlines[retention_days] = now_monotonic + MEDIA_ARCHIVE_CLEANUP_INTERVAL_SEC

    async def count_recent_media_records(self, retention_days: int = 3) -> int:
        await self.cleanup_media_archive(retention_days, force=True)
        row = await self.fetchone(
            queries.COUNT_RECENT_MEDIA_ARCHIVE,
            (self._days_ago(retention_days),),
        )
        return int(row["count"]) if row else 0

    async def get_recent_media_records(
        self,
        retention_days: int = 3,
        limit: int = 5,
        offset: int = 0,
    ) -> list[aiosqlite.Row]:
        await self.cleanup_media_archive(retention_days, force=True)
        return await self.fetchall(
            queries.SELECT_RECENT_MEDIA_ARCHIVE,
            (self._days_ago(retention_days), limit, offset),
        )

    async def get_media_record_by_id(self, media_id: int) -> Optional[aiosqlite.Row]:
        return await self.fetchone(queries.SELECT_MEDIA_ARCHIVE_BY_ID, (media_id,))

    async def delete_media_record(self, media_id: int) -> None:
        await self.execute(queries.DELETE_MEDIA_ARCHIVE_BY_ID, (media_id,))

    async def add_virtual_memory(
        self,
        pair_id: int,
        user_id: int,
        companion_id: int,
        speaker: str,
        content: str,
        keep_last: int = 12,
    ) -> None:
        normalized = " ".join((content or "").split()).strip()
        if not normalized:
            return
        assert self._conn is not None
        try:
            await self._conn.execute("BEGIN")
            await self._conn.execute(
                queries.INSERT_VIRTUAL_DIALOG_MEMORY,
                (pair_id, user_id, companion_id, speaker, normalized, self._now()),
            )
            await self._conn.execute(
                queries.DELETE_OLD_VIRTUAL_DIALOG_MEMORY,
                (pair_id, pair_id, keep_last),
            )
            await self._conn.commit()
        except Exception:
            await self._conn.rollback()
            raise

    async def get_virtual_memory(self, pair_id: int, limit: int = 10) -> list[aiosqlite.Row]:
        rows = await self.fetchall(queries.SELECT_VIRTUAL_DIALOG_MEMORY, (pair_id, limit))
        return list(reversed(rows))

    async def add_broadcast_log(
        self,
        audience: str,
        message: str,
        sent_count: int,
        failed_count: int,
        created_by: int | None,
    ) -> None:
        await self.execute(
            queries.INSERT_BROADCAST,
            (audience, message, sent_count, failed_count, created_by, self._now()),
        )

    async def get_recent_broadcasts(self, limit: int = 8) -> list[aiosqlite.Row]:
        return await self.fetchall(queries.SELECT_RECENT_BROADCASTS, (limit,))

    async def get_broadcast_user_ids(self, audience: str) -> list[int]:
        if audience == "promo":
            rows = await self.fetchall(
                queries.SELECT_BROADCAST_NON_PREMIUM_USER_IDS,
                (self._now(), self._now()),
            )
        elif audience == "inactive":
            rows = await self.fetchall(
                queries.SELECT_BROADCAST_INACTIVE_USER_IDS,
                (self._now(), self._days_ago(3)),
            )
        else:
            rows = await self.fetchall(
                queries.SELECT_BROADCAST_ALL_USER_IDS,
                (self._now(),),
            )
        return [int(row["user_id"]) for row in rows]

    async def stats(self) -> dict[str, int]:
        users = await self.fetchone(queries.STATS_USERS)
        active_chats = await self.fetchone(queries.STATS_ACTIVE_CHATS)
        queue = await self.fetchone(queries.STATS_QUEUE)
        reports = await self.fetchone(queries.STATS_REPORTS)
        banned_perm = await self.fetchone(queries.STATS_BANNED)
        banned_temp = await self.fetchone(queries.STATS_TEMP_BANNED, (self._now(),))
        new_users_24h = await self.fetchone(queries.COUNT_USERS_CREATED_SINCE, (self._days_ago(1),))
        new_users_7d = await self.fetchone(queries.COUNT_USERS_CREATED_SINCE, (self._days_ago(7),))
        active_users_24h = await self.fetchone(queries.COUNT_USERS_SEEN_SINCE, (self._days_ago(1),))
        engaged_users = await self.fetchone(queries.COUNT_USERS_WITH_CHATS)
        premium_active = await self.fetchone(queries.COUNT_PREMIUM_ACTIVE, (self._now(),))
        premium_buyers = await self.fetchone(queries.COUNT_PREMIUM_BUYERS)
        premium_purchases = await self.fetchone(queries.COUNT_PAYMENT_INCIDENTS)
        promo_users = await self.fetchone(queries.COUNT_PROMO_USERS)
        promo_codes = await self.fetchone(queries.COUNT_PROMO_CODES)
        virtual_users = await self.fetchone(queries.COUNT_VIRTUAL_CHAT_USERS)
        active_virtual_chats = await self.fetchone(queries.COUNT_ACTIVE_VIRTUAL_CHATS)
        payment_rows = await self.fetchall(queries.SELECT_PAYMENT_INCIDENTS)
        banned = (int(banned_perm["count"]) if banned_perm else 0) + (
            int(banned_temp["count"]) if banned_temp else 0
        )
        revenue_xtr = sum(self._payment_amount_from_payload(row["payload"] or "") for row in payment_rows)
        return {
            "users": int(users["count"]) if users else 0,
            "active_chats": int(active_chats["count"]) if active_chats else 0,
            "queue": int(queue["count"]) if queue else 0,
            "reports": int(reports["count"]) if reports else 0,
            "banned": banned,
            "new_users_24h": int(new_users_24h["count"]) if new_users_24h else 0,
            "new_users_7d": int(new_users_7d["count"]) if new_users_7d else 0,
            "active_users_24h": int(active_users_24h["count"]) if active_users_24h else 0,
            "engaged_users": int(engaged_users["count"]) if engaged_users else 0,
            "premium_active": int(premium_active["count"]) if premium_active else 0,
            "premium_buyers": int(premium_buyers["count"]) if premium_buyers else 0,
            "premium_purchases": int(premium_purchases["count"]) if premium_purchases else 0,
            "promo_users": int(promo_users["count"]) if promo_users else 0,
            "promo_codes": int(promo_codes["count"]) if promo_codes else 0,
            "virtual_users": int(virtual_users["count"]) if virtual_users else 0,
            "active_virtual_chats": int(active_virtual_chats["count"]) if active_virtual_chats else 0,
            "revenue_xtr": revenue_xtr,
        }

    async def get_active_user_ids(self) -> list[int]:
        rows = await self.fetchall(queries.SELECT_ACTIVE_USERS, (self._now(),))
        return [int(row["user_id"]) for row in rows]

    async def get_all_user_ids(self) -> list[int]:
        rows = await self.fetchall(queries.SELECT_ALL_USERS)
        return [int(row["user_id"]) for row in rows]

    async def get_all_users(self) -> list[aiosqlite.Row]:
        return await self.fetchall(queries.SELECT_ALL_USERS)

    async def search_users(self, query: str, limit: int = 10) -> list[aiosqlite.Row]:
        normalized = query.strip().lstrip("@")
        if not normalized:
            return []
        wildcard = f"%{normalized}%"
        return await self.fetchall(
            queries.SEARCH_USERS,
            (
                normalized,
                normalized,
                wildcard,
                wildcard,
                wildcard,
                wildcard,
                normalized,
                normalized,
                limit,
            ),
        )

    async def get_recent_incidents_for_user(
        self,
        user_id: int,
        limit: int = 15,
    ) -> list[aiosqlite.Row]:
        return await self.fetchall(queries.SELECT_RECENT_INCIDENTS_FOR_USER, (user_id, user_id, limit))

    async def count_incidents_for_user(self, user_id: int) -> int:
        row = await self.fetchone(queries.COUNT_INCIDENTS_FOR_USER, (user_id, user_id))
        return int(row["count"]) if row else 0

    async def count_virtual_chats_for_user(self, user_id: int) -> int:
        row = await self.fetchone(queries.COUNT_VIRTUAL_CHATS_FOR_USER, (user_id, user_id))
        return int(row["count"]) if row else 0

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
        cached = self._lang_cache.get(user_id)
        if cached in {"ru", "en"}:
            return cached
        row = await self.fetchone(queries.SELECT_LANG, (user_id,))
        if not row:
            return "ru"
        value = (row["lang"] or "").strip().lower()
        normalized = value if value in {"ru", "en"} else "ru"
        self._lang_cache[user_id] = normalized
        return normalized

    async def set_lang(self, user_id: int, lang: str) -> None:
        normalized = lang.strip().lower()
        if normalized not in {"ru", "en"}:
            normalized = "ru"
        await self.execute(queries.UPDATE_LANG, (normalized, user_id))
        self._lang_cache[user_id] = normalized

    async def get_all_premium_until(self) -> list[str]:
        rows = await self.fetchall(queries.SELECT_ALL_PREMIUM_UNTIL)
        return [row["premium_until"] for row in rows]

    def _payment_amount_from_payload(self, payload: str) -> int:
        normalized = (payload or "").strip()
        if not normalized:
            return 0

        if "|" in normalized:
            parts = normalized.split("|")
            if len(parts) >= 2:
                try:
                    return int(parts[1])
                except ValueError:
                    return 0

        if ":" in normalized and normalized.startswith("premium_"):
            maybe_amount = normalized.split(":")[-1]
            try:
                return int(maybe_amount)
            except ValueError:
                pass

        if normalized.startswith("premium_"):
            try:
                days = int(normalized.split("_", 1)[1])
            except (IndexError, ValueError):
                return 0
            return {7: 29, 30: 99, 90: 249}.get(days, 0)

        return 0
