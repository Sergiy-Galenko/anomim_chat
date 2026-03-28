from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from . import queries

MigrationApplyFn = Callable[[Any], Awaitable[None]]

REPORT_STATUS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_reports_status_created_at ON reports(status, created_at)
"""

INITIAL_SCHEMA_SQL = queries.CREATE_TABLES.replace(
    "CREATE INDEX IF NOT EXISTS idx_reports_status_created_at ON reports(status, created_at);\n",
    "",
)

USER_COLUMN_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("username", "TEXT NOT NULL DEFAULT ''"),
    ("first_name", "TEXT NOT NULL DEFAULT ''"),
    ("last_name", "TEXT NOT NULL DEFAULT ''"),
    ("last_seen_at", "TEXT NOT NULL DEFAULT ''"),
    ("banned_until", "TEXT NOT NULL DEFAULT ''"),
    ("muted_until", "TEXT NOT NULL DEFAULT ''"),
    ("interests", "TEXT NOT NULL DEFAULT ''"),
    ("only_interest", "INTEGER NOT NULL DEFAULT 0"),
    ("premium_until", "TEXT NOT NULL DEFAULT ''"),
    ("trial_used", "INTEGER NOT NULL DEFAULT 0"),
    ("skip_until", "TEXT NOT NULL DEFAULT ''"),
    ("auto_search", "INTEGER NOT NULL DEFAULT 0"),
    ("content_filter", "INTEGER NOT NULL DEFAULT 1"),
    ("lang", "TEXT NOT NULL DEFAULT 'ru'"),
)

REPORT_COLUMN_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("status", "TEXT NOT NULL DEFAULT 'new'"),
    ("resolved_at", "TEXT"),
    ("resolved_by", "BIGINT"),
)


@dataclass(frozen=True, slots=True)
class Migration:
    version: str
    description: str
    apply_sqlite: MigrationApplyFn
    apply_postgres: MigrationApplyFn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _split_sql_script(script: str) -> list[str]:
    return [statement.strip() for statement in script.split(";") if statement.strip()]


def build_postgres_schema(sqlite_schema: str) -> str:
    return (
        sqlite_schema.replace(
            "INTEGER PRIMARY KEY AUTOINCREMENT",
            "BIGSERIAL PRIMARY KEY",
        ).replace(
            "INTEGER PRIMARY KEY",
            "BIGINT PRIMARY KEY",
        )
    )


async def _apply_sqlite_script(connection: Any, script: str) -> None:
    for statement in _split_sql_script(script):
        await connection.execute(statement)


async def _apply_postgres_script(connection: Any, script: str) -> None:
    for statement in _split_sql_script(script):
        await connection.execute(statement)


async def _get_sqlite_columns(connection: Any, table: str) -> set[str]:
    async with connection.execute(f"PRAGMA table_info({table})") as cursor:
        rows = await cursor.fetchall()
    return {row["name"] for row in rows}


async def _add_missing_sqlite_columns(
    connection: Any,
    table: str,
    columns: tuple[tuple[str, str], ...],
) -> None:
    existing = await _get_sqlite_columns(connection, table)
    for column_name, definition in columns:
        if column_name in existing:
            continue
        await connection.execute(
            f"ALTER TABLE {table} ADD COLUMN {column_name} {definition}"
        )


async def _add_missing_postgres_columns(
    connection: Any,
    table: str,
    columns: tuple[tuple[str, str], ...],
) -> None:
    for column_name, definition in columns:
        await connection.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column_name} {definition}"
        )


async def _apply_initial_schema_sqlite(connection: Any) -> None:
    await _apply_sqlite_script(connection, INITIAL_SCHEMA_SQL)


async def _apply_initial_schema_postgres(connection: Any) -> None:
    await _apply_postgres_script(connection, build_postgres_schema(INITIAL_SCHEMA_SQL))


async def _apply_user_columns_sqlite(connection: Any) -> None:
    await _add_missing_sqlite_columns(connection, "users", USER_COLUMN_DEFINITIONS)


async def _apply_user_columns_postgres(connection: Any) -> None:
    await _add_missing_postgres_columns(connection, "users", USER_COLUMN_DEFINITIONS)


async def _apply_report_columns_sqlite(connection: Any) -> None:
    await _add_missing_sqlite_columns(connection, "reports", REPORT_COLUMN_DEFINITIONS)
    await connection.execute(REPORT_STATUS_INDEX_SQL)


async def _apply_report_columns_postgres(connection: Any) -> None:
    await _add_missing_postgres_columns(connection, "reports", REPORT_COLUMN_DEFINITIONS)
    await connection.execute(REPORT_STATUS_INDEX_SQL)


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version="0001",
        description="initial_schema",
        apply_sqlite=_apply_initial_schema_sqlite,
        apply_postgres=_apply_initial_schema_postgres,
    ),
    Migration(
        version="0002",
        description="users_profile_and_flags",
        apply_sqlite=_apply_user_columns_sqlite,
        apply_postgres=_apply_user_columns_postgres,
    ),
    Migration(
        version="0003",
        description="reports_resolution_fields",
        apply_sqlite=_apply_report_columns_sqlite,
        apply_postgres=_apply_report_columns_postgres,
    ),
)


async def _ensure_migration_table(connection: Any, dialect: str) -> None:
    statement = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TEXT NOT NULL
)
"""
    if dialect == "sqlite":
        await connection.execute(statement)
        return
    await connection.execute(statement)


async def _get_applied_versions(connection: Any, dialect: str) -> set[str]:
    statement = "SELECT version FROM schema_migrations"
    if dialect == "sqlite":
        async with connection.execute(statement) as cursor:
            rows = await cursor.fetchall()
        return {row["version"] for row in rows}
    rows = await connection.fetch(statement)
    return {row["version"] for row in rows}


async def _record_migration(connection: Any, dialect: str, migration: Migration) -> None:
    applied_at = _now()
    if dialect == "sqlite":
        await connection.execute(
            """
INSERT INTO schema_migrations (version, description, applied_at)
VALUES (?, ?, ?)
""",
            (migration.version, migration.description, applied_at),
        )
        return
    await connection.execute(
        """
INSERT INTO schema_migrations (version, description, applied_at)
VALUES ($1, $2, $3)
""",
        migration.version,
        migration.description,
        applied_at,
    )


async def apply_migrations(connection: Any, dialect: str) -> None:
    if dialect not in {"sqlite", "postgres"}:
        raise ValueError(f"Unsupported database dialect: {dialect}")

    await _ensure_migration_table(connection, dialect)
    applied_versions = await _get_applied_versions(connection, dialect)

    for migration in MIGRATIONS:
        if migration.version in applied_versions:
            continue
        if dialect == "sqlite":
            await migration.apply_sqlite(connection)
        else:
            await migration.apply_postgres(connection)
        await _record_migration(connection, dialect, migration)
