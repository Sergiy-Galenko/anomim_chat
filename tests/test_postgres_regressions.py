"""Optional integration tests; each test creates and removes its own schema.

Run with ANOMIM_TEST_POSTGRES_DSN pointing to a disposable PostgreSQL server.
"""
import asyncio
import os
import unittest
import uuid
from datetime import datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import asyncpg

from src.db.database import Database
from src.db.migrations import INITIAL_SCHEMA_SQL


@unittest.skipUnless(os.environ.get("ANOMIM_TEST_POSTGRES_DSN"), "No isolated PostgreSQL test server configured")
class PostgresRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        dsn = os.environ["ANOMIM_TEST_POSTGRES_DSN"]
        self.schema = "regression_" + uuid.uuid4().hex
        self.admin = await asyncpg.connect(dsn)
        await self.admin.execute(f'CREATE SCHEMA "{self.schema}"')
        parsed = urlsplit(dsn)
        query = dict(parse_qsl(parsed.query))
        query["search_path"] = self.schema
        self.dsn = urlunsplit(parsed._replace(query=urlencode(query)))
        self.databases = []

    async def asyncTearDown(self):
        for db in self.databases:
            await db.close()
        await self.admin.execute(f'DROP SCHEMA "{self.schema}" CASCADE')
        await self.admin.close()

    async def database(self):
        db = Database(self.dsn)
        self.databases.append(db)
        await db.connect()
        return db

    async def seed(self, db, users=(1, 2, 3)):
        for user_id in users:
            await db.create_user_if_missing(user_id)
            await db.queue_user_for_search(user_id)

    async def test_existing_schema_upgrade_preserves_data_and_accepts_large_ids(self):
        legacy = INITIAL_SCHEMA_SQL.replace(
            "INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY"
        ).replace("INTEGER PRIMARY KEY", "BIGINT PRIMARY KEY")
        connection = await asyncpg.connect(self.dsn)
        try:
            await connection.execute(legacy)
            await connection.execute("""
                CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, description TEXT NOT NULL, applied_at TEXT NOT NULL);
                INSERT INTO schema_migrations VALUES ('0001', 'initial_schema', ''),
                    ('0002', 'users_profile_and_flags', ''), ('0003', 'reports_resolution_fields', '');
                INSERT INTO users (user_id, created_at, state, rating) VALUES (1, '', 'idle', 7);
                INSERT INTO pairs (user1_id, user2_id, started_at, is_active) VALUES (1, 2, '', 0);
            """)
        finally:
            await connection.close()
        db = await self.database()
        self.assertEqual((await db.get_user(1))["rating"], 7)
        self.assertEqual((await db.fetchone("SELECT COUNT(*) AS n FROM pairs"))["n"], 1)
        columns = await self.admin.fetch(
            "SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema = $1",
            self.schema,
        )
        for column in columns:
            if column["column_name"].endswith("_id") and column["column_name"] not in {"file_id", "charge_id"} or column["column_name"] in {"created_by", "resolved_by"}:
                self.assertEqual(column["data_type"], "bigint", str(dict(column)))
        large_id = 5_000_000_001
        await self.seed(db, (1, large_id))
        match = await db.finalize_match(large_id, 1, is_virtual=False)
        self.assertIsNotNone(match)
        await db.add_media_record(large_id, 1, "photo", "fake-file")
        await db.add_incident(large_id, 1, "test", "")
        await db.end_chat_session(large_id)
        success, target = await db.submit_rating(1, 1, expected_pair_id=match.pair_id)
        self.assertTrue(success)
        self.assertEqual(target, large_id)
        await db.grant_paid_premium(large_id, 7, "premium_7|29|XTR", charge_id="large-user-payment")
        self.assertTrue(await db.get_premium_until(large_id))
        # A second cold start must leave migrated data intact.
        other = await self.database()
        self.assertEqual((await other.get_user(large_id))["rating"], 1)

    async def test_two_instances_cannot_match_the_same_candidate(self):
        first, second = await asyncio.gather(self.database(), self.database())
        await self.seed(first)
        for db in (first, second):
            original = db.get_user_snapshot

            async def slow_snapshot(user_id, *, connection=None, original=original):
                row = await original(user_id, connection=connection)
                if user_id == 2 and connection is not None:
                    await asyncio.sleep(0.02)
                return row

            db.get_user_snapshot = slow_snapshot
        for _ in range(8):
            results = await asyncio.gather(
                first.finalize_match(1, 2, is_virtual=False),
                second.finalize_match(3, 2, is_virtual=False),
            )
            self.assertEqual(sum(result is not None for result in results), 1)
            self.assertEqual((await first.fetchone("SELECT COUNT(*) AS n FROM pairs WHERE is_active = 1"))["n"], 1)
            await first.end_chat_session(2, collect_feedback=False)
            for user_id in (1, 2, 3):
                await first.queue_user_for_search(user_id)

    async def test_payment_deduplication_survives_separate_instances(self):
        first, second = await asyncio.gather(self.database(), self.database())
        await first.create_user_if_missing(1)
        results = await asyncio.gather(
            first.grant_paid_premium(1, 7, "premium_7|29|XTR", charge_id="charge-a"),
            second.grant_paid_premium(1, 7, "premium_7|29|XTR", charge_id="charge-a"),
        )
        self.assertEqual(results[0], results[1])
        self.assertEqual((await first.fetchone("SELECT COUNT(*) AS n FROM payments"))["n"], 1)
        await asyncio.gather(
            first.grant_paid_premium(1, 7, "premium_7|29|XTR", charge_id="charge-b"),
            second.grant_paid_premium(1, 7, "premium_7|29|XTR", charge_id="charge-c"),
        )
        self.assertEqual(
            datetime.fromisoformat(await first.get_premium_until(1)) - datetime.fromisoformat(results[0]),
            timedelta(days=14),
        )

    async def test_cancel_search_and_matching_keep_consistent_state(self):
        first, second = await asyncio.gather(self.database(), self.database())
        await self.seed(first)
        match, cancelled = await asyncio.gather(
            first.finalize_match(1, 2, is_virtual=False), second.cancel_search(2),
        )
        self.assertNotEqual(match is not None, cancelled)
        if match is not None:
            self.assertEqual((await first.get_user(2))["state"], "chatting")
        else:
            self.assertEqual((await first.get_user(2))["state"], "idle")
            self.assertIsNone(await first.get_active_pair(2))
        self.assertEqual(await first.get_queue_joined_at(2), "")


if __name__ == "__main__":
    unittest.main()
