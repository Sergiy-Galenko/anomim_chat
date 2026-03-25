from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import monotonic
from typing import Any, Optional

import aiosqlite

try:
    import asyncpg
except ModuleNotFoundError:  # pragma: no cover - optional production dependency
    asyncpg = None

from . import queries

DEFAULT_VIRTUAL_COMPANION_IDS = (-101, -102, -103, -104, -105)
DEFAULT_VIRTUAL_QUEUE_THRESHOLD = 4
DEFAULT_VIRTUAL_AB_VARIANTS = ("spark", "soft", "bold")
USER_CONTEXT_TOUCH_INTERVAL_SEC = 30.0
MEDIA_ARCHIVE_CLEANUP_INTERVAL_SEC = 3600.0
MATCH_CANDIDATES_LIMIT = 64

POSTGRES_QUERY_OVERRIDES = {
    queries.INSERT_USER: """
INSERT INTO users (user_id, created_at, state, is_banned, rating, chats_count)
VALUES (?, ?, ?, 0, 0, 0)
ON CONFLICT(user_id) DO NOTHING
""",
    queries.INSERT_QUEUE: """
INSERT INTO queue (user_id, joined_at)
VALUES (?, ?)
ON CONFLICT(user_id) DO UPDATE SET joined_at = EXCLUDED.joined_at
""",
    queries.INSERT_PENDING_RATING: """
INSERT INTO pending_ratings (user_id, pair_id, target_id, created_at)
VALUES (?, ?, ?, ?)
ON CONFLICT(user_id) DO UPDATE SET
    pair_id = EXCLUDED.pair_id,
    target_id = EXCLUDED.target_id,
    created_at = EXCLUDED.created_at
""",
    queries.INSERT_VIRTUAL_AB_SESSION: """
INSERT INTO virtual_ab_sessions (
    pair_id,
    user_id,
    companion_id,
    variant_key,
    started_at,
    ended_at,
    user_messages,
    companion_messages,
    media_messages,
    ended_by_user
)
VALUES (?, ?, ?, ?, ?, '', 0, 0, 0, 0)
ON CONFLICT(pair_id) DO UPDATE SET
    user_id = EXCLUDED.user_id,
    companion_id = EXCLUDED.companion_id,
    variant_key = EXCLUDED.variant_key,
    started_at = EXCLUDED.started_at,
    ended_at = EXCLUDED.ended_at,
    user_messages = EXCLUDED.user_messages,
    companion_messages = EXCLUDED.companion_messages,
    media_messages = EXCLUDED.media_messages,
    ended_by_user = EXCLUDED.ended_by_user
""",
}

POSTGRES_INSERT_PAIR = """
INSERT INTO pairs (user1_id, user2_id, started_at, ended_at, is_active)
VALUES (?, ?, ?, NULL, 1)
RETURNING id
"""


def _build_postgres_schema() -> str:
    return (
        queries.CREATE_TABLES.replace(
            "INTEGER PRIMARY KEY AUTOINCREMENT",
            "BIGSERIAL PRIMARY KEY",
        ).replace(
            "INTEGER PRIMARY KEY",
            "BIGINT PRIMARY KEY",
        )
    )


POSTGRES_CREATE_TABLES = _build_postgres_schema()


@dataclass(slots=True)
class MatchCommitResult:
    pair_id: int
    partner_id: int
    is_virtual: bool


@dataclass(slots=True)
class ChatCloseResult:
    pair_id: int
    partner_id: int
    partner_is_virtual: bool
    user_feedback_pending: bool
    partner_feedback_pending: bool


@dataclass(slots=True)
class PromoRedemptionResult:
    status: str
    days: int | None = None
    premium_until: str | None = None


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
        self._pool: Any = None
        self._dialect = "sqlite"
        self._compiled_query_cache: dict[str, str] = {}
        # Simple lock to serialize critical DB operations like matching.
        self.lock = asyncio.Lock()
        self._transaction_lock = asyncio.Lock()
        self._known_users: set[int] = set()
        self._lang_cache: dict[int, str] = {}
        self._user_touch_cache: dict[int, tuple[str, str, str, float]] = {}
        self._media_cleanup_deadlines: dict[int, float] = {}

    def _is_postgres_url(self) -> bool:
        normalized = self.db_path.strip().lower()
        return normalized.startswith("postgres://") or normalized.startswith("postgresql://")

    def _is_postgres(self) -> bool:
        return self._dialect == "postgres"

    def _resolve_db_file(self) -> Optional[Path]:
        if (
            not self.db_path
            or self.db_path == ":memory:"
            or self.db_path.startswith("file:")
            or self._is_postgres_url()
        ):
            return None
        return Path(self.db_path).expanduser()

    async def connect(self) -> None:
        if self._is_postgres_url():
            await self._connect_postgres()
            return

        db_file = self._resolve_db_file()
        if db_file is not None:
            db_file.parent.mkdir(parents=True, exist_ok=True)

        self._dialect = "sqlite"
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
            self._conn = None
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def _connect_postgres(self) -> None:
        if asyncpg is None:
            raise RuntimeError(
                "PostgreSQL backend requires asyncpg. Install dependencies from requirements.txt."
            )
        self._dialect = "postgres"
        self._pool = await asyncpg.create_pool(dsn=self.db_path, min_size=1, max_size=10)
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for statement in self._split_sql_script(POSTGRES_CREATE_TABLES):
                    await conn.execute(statement)
                await self._ensure_columns(connection=conn)
                await self._ensure_report_columns(connection=conn)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _days_ago(self, days: int) -> str:
        return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    def _parse_iso(self, value: str) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _is_active_until(self, value: str) -> bool:
        dt = self._parse_iso(value)
        if not dt:
            return False
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt > datetime.now(timezone.utc)

    def _extend_until(self, current_until: str, days: int) -> str:
        now = datetime.now(timezone.utc)
        if days <= 0:
            return current_until
        dt = self._parse_iso(current_until)
        if dt:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            base = dt if dt > now else now
        else:
            base = now
        return (base + timedelta(days=days)).isoformat()

    def _remember_user(self, user_id: int) -> None:
        self._known_users.add(user_id)

    def _normalize_lang(self, value: str | None) -> str:
        normalized = (value or "").strip().lower()
        return normalized if normalized in {"ru", "en", "uk", "de"} else "ru"

    def _prime_user_cache(self, row: Any) -> None:
        user_id = int(row["user_id"])
        self._remember_user(user_id)
        keys = set(row.keys()) if hasattr(row, "keys") else set()
        if "lang" in keys:
            self._lang_cache[user_id] = self._normalize_lang(row["lang"])

    def _resolve_query(self, query: str) -> str:
        if not self._is_postgres():
            return query
        resolved = POSTGRES_QUERY_OVERRIDES.get(query, query)
        cached = self._compiled_query_cache.get(resolved)
        if cached is not None:
            return cached

        parts: list[str] = []
        index = 1
        for char in resolved:
            if char == "?":
                parts.append(f"${index}")
                index += 1
            else:
                parts.append(char)
        compiled = "".join(parts)
        self._compiled_query_cache[resolved] = compiled
        return compiled

    def _split_sql_script(self, script: str) -> list[str]:
        return [statement.strip() for statement in script.split(";") if statement.strip()]

    @asynccontextmanager
    async def transaction(self):
        if self._is_postgres():
            assert self._pool is not None
            async with self._pool.acquire() as connection:
                async with connection.transaction():
                    yield connection
            return

        assert self._conn is not None
        async with self._transaction_lock:
            await self._conn.execute("BEGIN")
            try:
                yield self._conn
            except Exception:
                await self._conn.rollback()
                raise
            else:
                await self._conn.commit()

    async def _fetchone_impl(
        self,
        query: str,
        params: tuple[Any, ...] = (),
        *,
        connection: Any = None,
    ) -> Any:
        if self._is_postgres():
            compiled = self._resolve_query(query)
            if connection is not None:
                return await connection.fetchrow(compiled, *params)
            assert self._pool is not None
            async with self._pool.acquire() as db_conn:
                return await db_conn.fetchrow(compiled, *params)

        db_conn = connection or self._conn
        assert db_conn is not None
        async with db_conn.execute(query, params) as cursor:
            return await cursor.fetchone()

    async def _fetchall_impl(
        self,
        query: str,
        params: tuple[Any, ...] = (),
        *,
        connection: Any = None,
    ) -> list[Any]:
        if self._is_postgres():
            compiled = self._resolve_query(query)
            if connection is not None:
                return list(await connection.fetch(compiled, *params))
            assert self._pool is not None
            async with self._pool.acquire() as db_conn:
                return list(await db_conn.fetch(compiled, *params))

        db_conn = connection or self._conn
        assert db_conn is not None
        async with db_conn.execute(query, params) as cursor:
            return await cursor.fetchall()

    async def _execute_impl(
        self,
        query: str,
        params: tuple[Any, ...] = (),
        *,
        connection: Any = None,
        commit: bool = True,
    ) -> Any:
        if self._is_postgres():
            compiled = self._resolve_query(query)
            if connection is not None:
                return await connection.execute(compiled, *params)
            assert self._pool is not None
            async with self._pool.acquire() as db_conn:
                return await db_conn.execute(compiled, *params)

        db_conn = connection or self._conn
        assert db_conn is not None
        result = await db_conn.execute(query, params)
        if commit and connection is None:
            await db_conn.commit()
        return result

    async def _ensure_columns(self, connection: Any = None) -> None:
        if self._is_postgres():
            db_conn = connection
            assert db_conn is not None
            statements = (
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen_at TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_until TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS muted_until TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS interests TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS only_interest INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS premium_until TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS trial_used INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS skip_until TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS auto_search INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS content_filter INTEGER NOT NULL DEFAULT 1",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS lang TEXT NOT NULL DEFAULT 'ru'",
            )
            for statement in statements:
                await db_conn.execute(statement)
            return

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

    async def _ensure_report_columns(self, connection: Any = None) -> None:
        if self._is_postgres():
            db_conn = connection
            assert db_conn is not None
            statements = (
                "ALTER TABLE reports ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'new'",
                "ALTER TABLE reports ADD COLUMN IF NOT EXISTS resolved_at TEXT",
                "ALTER TABLE reports ADD COLUMN IF NOT EXISTS resolved_by BIGINT",
            )
            for statement in statements:
                await db_conn.execute(statement)
            return

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

    async def fetchone(
        self,
        query: str,
        params: tuple[Any, ...] = (),
        *,
        connection: Any = None,
    ) -> Any:
        return await self._fetchone_impl(query, params, connection=connection)

    async def fetchall(
        self,
        query: str,
        params: tuple[Any, ...] = (),
        *,
        connection: Any = None,
    ) -> list[Any]:
        return await self._fetchall_impl(query, params, connection=connection)

    async def execute(
        self,
        query: str,
        params: tuple[Any, ...] = (),
        *,
        commit: bool = True,
        connection: Any = None,
    ) -> None:
        await self._execute_impl(query, params, connection=connection, commit=commit)

    async def create_user_if_missing(self, user_id: int) -> None:
        if user_id in self._known_users:
            return
        await self.execute(queries.INSERT_USER, (user_id, self._now(), "idle"))
        self._remember_user(user_id)

    async def get_user(self, user_id: int) -> Any:
        row = await self.fetchone(queries.SELECT_USER, (user_id,))
        if row:
            self._prime_user_cache(row)
        return row

    async def get_user_snapshot(self, user_id: int, *, connection: Any = None) -> Any:
        row = await self.fetchone(
            queries.SELECT_USER_WITH_QUEUE,
            (user_id,),
            connection=connection,
        )
        if row:
            self._prime_user_cache(row)
        return row

    async def get_search_status_snapshot(self, user_id: int) -> Any:
        return await self.fetchone(queries.SELECT_SEARCH_STATUS, (user_id,))

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
        joined_at = self._now()
        async with self.transaction() as connection:
            await self.execute(
                queries.UPDATE_STATE,
                ("searching", user_id),
                commit=False,
                connection=connection,
            )
            await self.execute(
                queries.INSERT_QUEUE,
                (user_id, joined_at),
                commit=False,
                connection=connection,
            )

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

    async def get_queue_candidates_limited(
        self,
        exclude_user_id: int,
        *,
        limit: int = MATCH_CANDIDATES_LIMIT,
    ) -> list[Any]:
        return await self.fetchall(
            queries.SELECT_QUEUE_CANDIDATES_LIMITED,
            (
                exclude_user_id,
                exclude_user_id,
                exclude_user_id,
                self._now(),
                limit,
            ),
        )

    async def _insert_pair_row(self, user1_id: int, user2_id: int, *, connection: Any) -> int:
        started_at = self._now()
        if self._is_postgres():
            query = self._resolve_query(POSTGRES_INSERT_PAIR)
            return int(await connection.fetchval(query, user1_id, user2_id, started_at))
        cursor = await connection.execute(queries.INSERT_PAIR, (user1_id, user2_id, started_at))
        return int(cursor.lastrowid)

    async def create_pair(self, user1_id: int, user2_id: int) -> int:
        async with self.transaction() as connection:
            return await self._insert_pair_row(user1_id, user2_id, connection=connection)

    async def start_virtual_pair(self, user_id: int, companion_id: int) -> int:
        async with self.transaction() as connection:
            await self.execute(
                queries.DELETE_QUEUE,
                (user_id,),
                commit=False,
                connection=connection,
            )
            await self.execute(
                queries.UPDATE_STATE,
                ("chatting", user_id),
                commit=False,
                connection=connection,
            )
            pair_id = await self._insert_pair_row(user_id, companion_id, connection=connection)
            await self.execute(
                queries.INCREMENT_CHATS,
                (user_id,),
                commit=False,
                connection=connection,
            )
            return pair_id

    async def start_human_pair(self, user1_id: int, user2_id: int) -> int:
        async with self.transaction() as connection:
            await self.execute(
                queries.DELETE_QUEUE,
                (user1_id,),
                commit=False,
                connection=connection,
            )
            await self.execute(
                queries.DELETE_QUEUE,
                (user2_id,),
                commit=False,
                connection=connection,
            )
            await self.execute(
                queries.UPDATE_STATE,
                ("chatting", user1_id),
                commit=False,
                connection=connection,
            )
            await self.execute(
                queries.UPDATE_STATE,
                ("chatting", user2_id),
                commit=False,
                connection=connection,
            )
            pair_id = await self._insert_pair_row(user1_id, user2_id, connection=connection)
            await self.execute(
                queries.INCREMENT_CHATS,
                (user1_id,),
                commit=False,
                connection=connection,
            )
            await self.execute(
                queries.INCREMENT_CHATS,
                (user2_id,),
                commit=False,
                connection=connection,
            )
            return pair_id

    async def finalize_match(self, user_id: int, partner_id: int, *, is_virtual: bool) -> MatchCommitResult | None:
        async with self.lock:
            async with self.transaction() as connection:
                user = await self.get_user_snapshot(user_id, connection=connection)
                if not user or (user["state"] or "") != "searching" or not (user["joined_at"] or ""):
                    return None
                if bool(user["is_banned"]) or self._is_active_until(user["banned_until"] or ""):
                    return None

                if is_virtual:
                    await self.execute(
                        queries.DELETE_QUEUE,
                        (user_id,),
                        commit=False,
                        connection=connection,
                    )
                    await self.execute(
                        queries.UPDATE_STATE,
                        ("chatting", user_id),
                        commit=False,
                        connection=connection,
                    )
                    pair_id = await self._insert_pair_row(user_id, partner_id, connection=connection)
                    await self.execute(
                        queries.INCREMENT_CHATS,
                        (user_id,),
                        commit=False,
                        connection=connection,
                    )
                    return MatchCommitResult(pair_id=pair_id, partner_id=partner_id, is_virtual=True)

                partner = await self.get_user_snapshot(partner_id, connection=connection)
                if (
                    not partner
                    or (partner["state"] or "") != "searching"
                    or not (partner["joined_at"] or "")
                    or bool(partner["is_banned"])
                    or self._is_active_until(partner["banned_until"] or "")
                ):
                    return None

                await self.execute(
                    queries.DELETE_QUEUE,
                    (user_id,),
                    commit=False,
                    connection=connection,
                )
                await self.execute(
                    queries.DELETE_QUEUE,
                    (partner_id,),
                    commit=False,
                    connection=connection,
                )
                await self.execute(
                    queries.UPDATE_STATE,
                    ("chatting", user_id),
                    commit=False,
                    connection=connection,
                )
                await self.execute(
                    queries.UPDATE_STATE,
                    ("chatting", partner_id),
                    commit=False,
                    connection=connection,
                )
                pair_id = await self._insert_pair_row(user_id, partner_id, connection=connection)
                await self.execute(
                    queries.INCREMENT_CHATS,
                    (user_id,),
                    commit=False,
                    connection=connection,
                )
                await self.execute(
                    queries.INCREMENT_CHATS,
                    (partner_id,),
                    commit=False,
                    connection=connection,
                )
                return MatchCommitResult(pair_id=pair_id, partner_id=partner_id, is_virtual=False)

    async def get_active_pair(self, user_id: int, *, connection: Any = None) -> Any:
        return await self.fetchone(
            queries.SELECT_ACTIVE_PAIR,
            (user_id, user_id),
            connection=connection,
        )

    async def end_pair(self, pair_id: int) -> None:
        await self.execute(queries.END_PAIR_BY_ID, (self._now(), pair_id))

    async def add_report(self, reporter_id: int, reported_id: int, reason: str) -> None:
        await self.execute(queries.INSERT_REPORT, (reporter_id, reported_id, reason, self._now()))

    async def end_chat_session(
        self,
        user_id: int,
        *,
        notify_user: bool = True,
        notify_partner: bool = True,
        collect_feedback: bool = True,
        ended_by_user: bool = True,
    ) -> ChatCloseResult | None:
        async with self.lock:
            async with self.transaction() as connection:
                pair = await self.get_active_pair(user_id, connection=connection)
                if not pair:
                    return None

                pair_id = int(pair["id"])
                partner_id = int(pair["user2_id"] if int(pair["user1_id"]) == user_id else pair["user1_id"])
                partner_is_virtual = partner_id < 0
                user_feedback_pending = collect_feedback and notify_user and not partner_is_virtual
                partner_feedback_pending = collect_feedback and notify_partner and not partner_is_virtual

                if partner_is_virtual:
                    await self.execute(
                        queries.FINISH_VIRTUAL_AB_SESSION,
                        (self._now(), 1 if ended_by_user else 0, pair_id),
                        commit=False,
                        connection=connection,
                    )
                await self.execute(
                    queries.END_PAIR_BY_ID,
                    (self._now(), pair_id),
                    commit=False,
                    connection=connection,
                )
                await self.execute(
                    queries.UPDATE_STATE,
                    ("idle", user_id),
                    commit=False,
                    connection=connection,
                )
                if not partner_is_virtual:
                    await self.execute(
                        queries.UPDATE_STATE,
                        ("idle", partner_id),
                        commit=False,
                        connection=connection,
                    )

                await self.execute(
                    queries.DELETE_PENDING_RATING,
                    (user_id,),
                    commit=False,
                    connection=connection,
                )
                if not partner_is_virtual:
                    await self.execute(
                        queries.DELETE_PENDING_RATING,
                        (partner_id,),
                        commit=False,
                        connection=connection,
                    )

                if user_feedback_pending:
                    await self.execute(
                        queries.INSERT_PENDING_RATING,
                        (user_id, pair_id, partner_id, self._now()),
                        commit=False,
                        connection=connection,
                    )
                if partner_feedback_pending:
                    await self.execute(
                        queries.INSERT_PENDING_RATING,
                        (partner_id, pair_id, user_id, self._now()),
                        commit=False,
                        connection=connection,
                    )

                return ChatCloseResult(
                    pair_id=pair_id,
                    partner_id=partner_id,
                    partner_is_virtual=partner_is_virtual,
                    user_feedback_pending=user_feedback_pending,
                    partner_feedback_pending=partner_feedback_pending,
                )

    async def skip_chat_session(self, user_id: int, *, skip_until: str) -> ChatCloseResult | None:
        async with self.lock:
            async with self.transaction() as connection:
                pair = await self.get_active_pair(user_id, connection=connection)
                if not pair:
                    return None

                pair_id = int(pair["id"])
                partner_id = int(pair["user2_id"] if int(pair["user1_id"]) == user_id else pair["user1_id"])
                partner_is_virtual = partner_id < 0
                now_iso = self._now()

                await self.execute(
                    queries.UPDATE_SKIP_UNTIL,
                    (skip_until, user_id),
                    commit=False,
                    connection=connection,
                )
                if partner_is_virtual:
                    await self.execute(
                        queries.FINISH_VIRTUAL_AB_SESSION,
                        (now_iso, 1, pair_id),
                        commit=False,
                        connection=connection,
                    )
                await self.execute(
                    queries.END_PAIR_BY_ID,
                    (now_iso, pair_id),
                    commit=False,
                    connection=connection,
                )
                await self.execute(
                    queries.DELETE_PENDING_RATING,
                    (user_id,),
                    commit=False,
                    connection=connection,
                )
                if not partner_is_virtual:
                    await self.execute(
                        queries.DELETE_PENDING_RATING,
                        (partner_id,),
                        commit=False,
                        connection=connection,
                    )
                await self.execute(
                    queries.UPDATE_STATE,
                    ("searching", user_id),
                    commit=False,
                    connection=connection,
                )
                await self.execute(
                    queries.INSERT_QUEUE,
                    (user_id, now_iso),
                    commit=False,
                    connection=connection,
                )
                if not partner_is_virtual:
                    await self.execute(
                        queries.UPDATE_STATE,
                        ("idle", partner_id),
                        commit=False,
                        connection=connection,
                    )
                await self.execute(
                    queries.INSERT_INCIDENT,
                    (user_id, partner_id, "skip", "", now_iso),
                    commit=False,
                    connection=connection,
                )

                return ChatCloseResult(
                    pair_id=pair_id,
                    partner_id=partner_id,
                    partner_is_virtual=partner_is_virtual,
                    user_feedback_pending=False,
                    partner_feedback_pending=False,
                )

    async def report_chat_session(self, reporter_id: int, reason: str) -> ChatCloseResult | None:
        async with self.lock:
            async with self.transaction() as connection:
                pair = await self.get_active_pair(reporter_id, connection=connection)
                if not pair:
                    return None

                pair_id = int(pair["id"])
                reported_id = int(
                    pair["user2_id"] if int(pair["user1_id"]) == reporter_id else pair["user1_id"]
                )
                if reported_id < 0:
                    return None

                now_iso = self._now()
                await self.execute(
                    queries.INSERT_REPORT,
                    (reporter_id, reported_id, reason, now_iso),
                    commit=False,
                    connection=connection,
                )
                await self.execute(
                    queries.INSERT_INCIDENT,
                    (reporter_id, reported_id, "report", reason, now_iso),
                    commit=False,
                    connection=connection,
                )
                await self.execute(
                    queries.END_PAIR_BY_ID,
                    (now_iso, pair_id),
                    commit=False,
                    connection=connection,
                )
                await self.execute(
                    queries.UPDATE_STATE,
                    ("idle", reporter_id),
                    commit=False,
                    connection=connection,
                )
                await self.execute(
                    queries.UPDATE_STATE,
                    ("idle", reported_id),
                    commit=False,
                    connection=connection,
                )
                await self.execute(
                    queries.DELETE_PENDING_RATING,
                    (reporter_id,),
                    commit=False,
                    connection=connection,
                )
                await self.execute(
                    queries.DELETE_PENDING_RATING,
                    (reported_id,),
                    commit=False,
                    connection=connection,
                )

                return ChatCloseResult(
                    pair_id=pair_id,
                    partner_id=reported_id,
                    partner_is_virtual=False,
                    user_feedback_pending=False,
                    partner_feedback_pending=False,
                )

    async def cancel_search(self, user_id: int) -> bool:
        async with self.transaction() as connection:
            user = await self.get_user_snapshot(user_id, connection=connection)
            if not user or (user["state"] or "") != "searching":
                return False
            await self.execute(
                queries.DELETE_QUEUE,
                (user_id,),
                commit=False,
                connection=connection,
            )
            await self.execute(
                queries.UPDATE_STATE,
                ("idle", user_id),
                commit=False,
                connection=connection,
            )
            return True

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

    async def get_virtual_ab_settings(self) -> dict[str, list[str]]:
        default_variants = list(DEFAULT_VIRTUAL_AB_VARIANTS)
        raw_variants = await self.get_setting(
            "virtual_ab_active_variants",
            ",".join(default_variants),
        )

        active_variants: list[str] = []
        for chunk in raw_variants.split(","):
            variant_key = chunk.strip().lower()
            if variant_key in DEFAULT_VIRTUAL_AB_VARIANTS and variant_key not in active_variants:
                active_variants.append(variant_key)

        if not active_variants:
            active_variants = default_variants

        return {
            "available_variants": default_variants,
            "active_variants": active_variants,
        }

    async def set_virtual_ab_active_variants(self, variant_keys: list[str]) -> None:
        normalized: list[str] = []
        for variant_key in variant_keys:
            candidate = variant_key.strip().lower()
            if candidate in DEFAULT_VIRTUAL_AB_VARIANTS and candidate not in normalized:
                normalized.append(candidate)
        if not normalized:
            normalized = list(DEFAULT_VIRTUAL_AB_VARIANTS)
        await self.set_setting(
            "virtual_ab_active_variants",
            ",".join(normalized),
        )

    async def create_virtual_ab_session(
        self,
        pair_id: int,
        user_id: int,
        companion_id: int,
        variant_key: str,
    ) -> None:
        await self.execute(
            queries.INSERT_VIRTUAL_AB_SESSION,
            (pair_id, user_id, companion_id, variant_key.strip().lower(), self._now()),
        )

    async def get_virtual_ab_session(self, pair_id: int):
        return await self.fetchone(queries.SELECT_VIRTUAL_AB_SESSION, (pair_id,))

    async def increment_virtual_ab_user_message(self, pair_id: int, *, is_media: bool = False) -> None:
        await self.execute(
            queries.INCREMENT_VIRTUAL_AB_USER_MESSAGE,
            (1 if is_media else 0, pair_id),
        )

    async def increment_virtual_ab_companion_message(self, pair_id: int) -> None:
        await self.execute(queries.INCREMENT_VIRTUAL_AB_COMPANION_MESSAGE, (pair_id,))

    async def finish_virtual_ab_session(self, pair_id: int, *, ended_by_user: bool = False) -> None:
        await self.execute(
            queries.FINISH_VIRTUAL_AB_SESSION,
            (self._now(), 1 if ended_by_user else 0, pair_id),
        )

    async def get_virtual_ab_stats(self) -> dict[str, Any]:
        rows = await self.fetchall(queries.SELECT_ALL_VIRTUAL_AB_SESSIONS)
        aggregates: dict[str, dict[str, Any]] = {
            variant_key: {
                "key": variant_key,
                "sessions": 0,
                "active": 0,
                "retained": 0,
                "deep_retained": 0,
                "total_user_messages": 0,
                "total_messages": 0,
                "duration_samples": 0,
                "duration_minutes_total": 0.0,
                "early_exits": 0,
                "media_messages": 0,
            }
            for variant_key in DEFAULT_VIRTUAL_AB_VARIANTS
        }

        active_sessions = 0
        for row in rows:
            variant_key = (row["variant_key"] or "").strip().lower()
            if variant_key not in aggregates:
                aggregates[variant_key] = {
                    "key": variant_key or "unknown",
                    "sessions": 0,
                    "active": 0,
                    "retained": 0,
                    "deep_retained": 0,
                    "total_user_messages": 0,
                    "total_messages": 0,
                    "duration_samples": 0,
                    "duration_minutes_total": 0.0,
                    "early_exits": 0,
                    "media_messages": 0,
                }

            bucket = aggregates[variant_key]
            user_messages = int(row["user_messages"] or 0)
            companion_messages = int(row["companion_messages"] or 0)
            media_messages = int(row["media_messages"] or 0)
            ended_at = (row["ended_at"] or "").strip()

            bucket["sessions"] += 1
            bucket["total_user_messages"] += user_messages
            bucket["total_messages"] += user_messages + companion_messages
            bucket["media_messages"] += media_messages

            if user_messages >= 3:
                bucket["retained"] += 1
            if user_messages >= 6:
                bucket["deep_retained"] += 1

            if ended_at:
                if user_messages < 3:
                    bucket["early_exits"] += 1
                try:
                    started_at_dt = datetime.fromisoformat(row["started_at"])
                    ended_at_dt = datetime.fromisoformat(ended_at)
                    duration_minutes = max(
                        (ended_at_dt - started_at_dt).total_seconds() / 60.0,
                        0.0,
                    )
                    bucket["duration_samples"] += 1
                    bucket["duration_minutes_total"] += duration_minutes
                except ValueError:
                    pass
            else:
                bucket["active"] += 1
                active_sessions += 1

        variants: list[dict[str, Any]] = []
        ordered_keys = [*DEFAULT_VIRTUAL_AB_VARIANTS, *[key for key in aggregates if key not in DEFAULT_VIRTUAL_AB_VARIANTS]]
        for variant_key in ordered_keys:
            bucket = aggregates[variant_key]
            sessions = int(bucket["sessions"])
            avg_user_messages = bucket["total_user_messages"] / sessions if sessions else 0.0
            avg_total_messages = bucket["total_messages"] / sessions if sessions else 0.0
            avg_duration_minutes = (
                bucket["duration_minutes_total"] / bucket["duration_samples"]
                if bucket["duration_samples"]
                else 0.0
            )
            variants.append(
                {
                    "key": bucket["key"],
                    "sessions": sessions,
                    "active": int(bucket["active"]),
                    "retained": int(bucket["retained"]),
                    "deep_retained": int(bucket["deep_retained"]),
                    "retention_rate": (bucket["retained"] / sessions) * 100 if sessions else 0.0,
                    "deep_retention_rate": (bucket["deep_retained"] / sessions) * 100 if sessions else 0.0,
                    "avg_user_messages": avg_user_messages,
                    "avg_total_messages": avg_total_messages,
                    "avg_duration_minutes": avg_duration_minutes,
                    "early_exits": int(bucket["early_exits"]),
                    "media_messages": int(bucket["media_messages"]),
                }
            )

        return {
            "total_sessions": len(rows),
            "active_sessions": active_sessions,
            "variants": variants,
        }

    async def redeem_managed_promo_code(
        self,
        user_id: int,
        code: str,
    ) -> PromoRedemptionResult:
        normalized = code.upper()
        async with self.lock:
            async with self.transaction() as connection:
                promo = await self.fetchone(
                    queries.SELECT_PROMO_CODE,
                    (normalized,),
                    connection=connection,
                )
                if not promo:
                    return PromoRedemptionResult("invalid")
                if not bool(promo["is_active"]):
                    return PromoRedemptionResult("inactive")

                used = await self.fetchone(
                    queries.SELECT_PROMO_USE,
                    (user_id, normalized),
                    connection=connection,
                )
                if used:
                    return PromoRedemptionResult("used")

                usage_limit = int(promo["usage_limit"])
                used_count = int(promo["used_count"])
                if usage_limit > 0 and used_count >= usage_limit:
                    return PromoRedemptionResult("exhausted")

                current_row = await self.fetchone(
                    queries.SELECT_PREMIUM_UNTIL,
                    (user_id,),
                    connection=connection,
                )
                current_until = current_row["premium_until"] if current_row else ""
                days = int(promo["days"])
                new_until = self._extend_until(current_until, days)
                now_iso = self._now()

                await self.execute(
                    queries.INSERT_PROMO_USE,
                    (user_id, normalized, now_iso),
                    commit=False,
                    connection=connection,
                )
                await self.execute(
                    queries.UPDATE_PROMO_CODE_USAGE,
                    (normalized,),
                    commit=False,
                    connection=connection,
                )
                await self.execute(
                    queries.UPDATE_PREMIUM_UNTIL,
                    (new_until, user_id),
                    commit=False,
                    connection=connection,
                )
                await self.execute(
                    queries.INSERT_INCIDENT,
                    (user_id, None, "promo", normalized, now_iso),
                    commit=False,
                    connection=connection,
                )

                return PromoRedemptionResult("ok", days=days, premium_until=new_until)

    async def redeem_static_promo_code(self, user_id: int, code: str, days: int) -> PromoRedemptionResult:
        normalized = code.upper()
        async with self.lock:
            async with self.transaction() as connection:
                used = await self.fetchone(
                    queries.SELECT_PROMO_USE,
                    (user_id, normalized),
                    connection=connection,
                )
                if used:
                    return PromoRedemptionResult("used")

                current_row = await self.fetchone(
                    queries.SELECT_PREMIUM_UNTIL,
                    (user_id,),
                    connection=connection,
                )
                current_until = current_row["premium_until"] if current_row else ""
                new_until = self._extend_until(current_until, days)
                now_iso = self._now()

                await self.execute(
                    queries.INSERT_PROMO_USE,
                    (user_id, normalized, now_iso),
                    commit=False,
                    connection=connection,
                )
                await self.execute(
                    queries.UPDATE_PREMIUM_UNTIL,
                    (new_until, user_id),
                    commit=False,
                    connection=connection,
                )
                await self.execute(
                    queries.INSERT_INCIDENT,
                    (user_id, None, "promo", normalized, now_iso),
                    commit=False,
                    connection=connection,
                )

                return PromoRedemptionResult("ok", days=days, premium_until=new_until)

    async def activate_trial(self, user_id: int, days: int) -> PromoRedemptionResult:
        async with self.lock:
            async with self.transaction() as connection:
                user = await self.get_user_snapshot(user_id, connection=connection)
                if not user:
                    return PromoRedemptionResult("invalid")
                if bool(user["trial_used"]):
                    return PromoRedemptionResult("used")

                new_until = self._extend_until(user["premium_until"] or "", days)
                now_iso = self._now()
                await self.execute(
                    queries.UPDATE_PREMIUM_UNTIL,
                    (new_until, user_id),
                    commit=False,
                    connection=connection,
                )
                await self.execute(
                    queries.UPDATE_TRIAL_USED,
                    (1, user_id),
                    commit=False,
                    connection=connection,
                )
                await self.execute(
                    queries.INSERT_INCIDENT,
                    (user_id, None, "trial", f"{days}d", now_iso),
                    commit=False,
                    connection=connection,
                )
                return PromoRedemptionResult("ok", days=days, premium_until=new_until)

    async def grant_paid_premium(self, user_id: int, days: int, payload: str) -> str:
        async with self.lock:
            async with self.transaction() as connection:
                current_row = await self.fetchone(
                    queries.SELECT_PREMIUM_UNTIL,
                    (user_id,),
                    connection=connection,
                )
                current_until = current_row["premium_until"] if current_row else ""
                new_until = self._extend_until(current_until, days)
                now_iso = self._now()
                await self.execute(
                    queries.UPDATE_PREMIUM_UNTIL,
                    (new_until, user_id),
                    commit=False,
                    connection=connection,
                )
                await self.execute(
                    queries.INSERT_INCIDENT,
                    (user_id, None, "payment", payload, now_iso),
                    commit=False,
                    connection=connection,
                )
                return new_until

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
            async with self.transaction() as connection:
                pending = await self.fetchone(
                    queries.SELECT_PENDING_RATING,
                    (rater_id,),
                    connection=connection,
                )
                if not pending:
                    return False, None

                pair_id = int(pending["pair_id"])
                target_id = int(pending["target_id"])
                if expected_target_id is not None and target_id != expected_target_id:
                    return False, None

                exists = await self.fetchone(
                    queries.SELECT_CHAT_FEEDBACK_EXISTS,
                    (pair_id, rater_id),
                    connection=connection,
                )
                if exists:
                    await self.execute(
                        queries.DELETE_PENDING_RATING,
                        (rater_id,),
                        commit=False,
                        connection=connection,
                    )
                    return False, target_id

                await self.execute(
                    queries.INSERT_CHAT_FEEDBACK,
                    (pair_id, rater_id, target_id, value, self._now()),
                    commit=False,
                    connection=connection,
                )
                await self.execute(
                    queries.INCREMENT_RATING,
                    (value, target_id),
                    commit=False,
                    connection=connection,
                )
                await self.execute(
                    queries.DELETE_PENDING_RATING,
                    (rater_id,),
                    commit=False,
                    connection=connection,
                )

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
        now_monotonic = monotonic()
        cleanup_due = now_monotonic >= self._media_cleanup_deadlines.get(retention_days, 0.0)
        async with self.transaction() as connection:
            if cleanup_due:
                await self.execute(
                    queries.DELETE_OLD_MEDIA_ARCHIVE,
                    (self._days_ago(retention_days),),
                    commit=False,
                    connection=connection,
                )
            await self.execute(
                queries.INSERT_MEDIA_ARCHIVE,
                (sender_id, receiver_id, media_type, file_id, caption, self._now()),
                commit=False,
                connection=connection,
            )
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
        async with self.transaction() as connection:
            await self.execute(
                queries.INSERT_VIRTUAL_DIALOG_MEMORY,
                (pair_id, user_id, companion_id, speaker, normalized, self._now()),
                commit=False,
                connection=connection,
            )
            await self.execute(
                queries.DELETE_OLD_VIRTUAL_DIALOG_MEMORY,
                (pair_id, pair_id, keep_last),
                commit=False,
                connection=connection,
            )

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
        if cached in {"ru", "en", "uk", "de"}:
            return cached
        row = await self.fetchone(queries.SELECT_LANG, (user_id,))
        if not row:
            return "ru"
        normalized = self._normalize_lang(row["lang"])
        self._lang_cache[user_id] = normalized
        return normalized

    async def set_lang(self, user_id: int, lang: str) -> None:
        normalized = self._normalize_lang(lang)
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
