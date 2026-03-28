import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from src.bot.routers.chat import relay_message
from src.config import Config
from src.db.database import Database


class FakeBot:
    def __init__(self) -> None:
        self.sent_messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str, reply_markup=None) -> None:
        self.sent_messages.append((chat_id, text))


class FakeMessage:
    def __init__(self, user_id: int, bot: FakeBot, text: str) -> None:
        self.from_user = SimpleNamespace(
            id=user_id,
            username="sender",
            first_name="Sender",
            last_name="User",
        )
        self.bot = bot
        self.text = text
        self.caption = None
        self.photo = None
        self.video = None
        self.animation = None
        self.audio = None
        self.voice = None
        self.video_note = None
        self.sticker = None
        self.document = None
        self.answers: list[str] = []

    async def answer(self, text: str, reply_markup=None) -> None:
        self.answers.append(text)


class DatabaseSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = Database(":memory:")
        await self.db.connect()
        self.config = Config(
            token="test-token",
            admin_ids=[],
            db_path=":memory:",
            redis_url=None,
            promo_codes={},
            trial_days=3,
            telegram_proxy=None,
            telegram_timeout_sec=60.0,
            telegram_webhook_secret=None,
        )

    async def asyncTearDown(self) -> None:
        await self.db.close()

    async def _create_human_pair(self, user1_id: int = 1, user2_id: int = 2) -> None:
        await self.db.create_user_if_missing(user1_id)
        await self.db.create_user_if_missing(user2_id)
        await self.db.queue_user_for_search(user1_id)
        await self.db.queue_user_for_search(user2_id)
        result = await self.db.finalize_match(user1_id, user2_id, is_virtual=False)
        self.assertIsNotNone(result)

    async def test_end_chat_session_is_atomic_and_creates_feedback(self) -> None:
        await self._create_human_pair()

        close_result = await self.db.end_chat_session(
            1,
            notify_user=True,
            notify_partner=True,
            collect_feedback=True,
        )

        self.assertIsNotNone(close_result)
        self.assertIsNone(await self.db.get_active_pair(1))
        self.assertEqual(await self.db.get_pending_rating(1), (close_result.pair_id, 2))
        self.assertEqual(await self.db.get_pending_rating(2), (close_result.pair_id, 1))

        user1 = await self.db.get_user_snapshot(1)
        user2 = await self.db.get_user_snapshot(2)
        self.assertEqual(user1["state"], "idle")
        self.assertEqual(user2["state"], "idle")

    async def test_skip_chat_session_requeues_user_and_logs_incident(self) -> None:
        await self._create_human_pair()

        skip_until = (datetime.now(timezone.utc)).isoformat()
        skip_result = await self.db.skip_chat_session(1, skip_until=skip_until)

        self.assertIsNotNone(skip_result)
        self.assertIsNone(await self.db.get_active_pair(1))
        user1 = await self.db.get_user_snapshot(1)
        user2 = await self.db.get_user_snapshot(2)
        self.assertEqual(user1["state"], "searching")
        self.assertTrue(user1["joined_at"])
        self.assertEqual(user1["skip_until"], skip_until)
        self.assertEqual(user2["state"], "idle")

        incidents = await self.db.get_recent_incidents_for_user(1)
        self.assertTrue(any(row["type"] == "skip" for row in incidents))

    async def test_static_promo_redemption_is_single_use_and_atomic(self) -> None:
        await self.db.create_user_if_missing(1)

        first = await self.db.redeem_static_promo_code(1, "HELLO", 7)
        second = await self.db.redeem_static_promo_code(1, "HELLO", 7)

        self.assertEqual(first.status, "ok")
        self.assertEqual(second.status, "used")

        user = await self.db.get_user_snapshot(1)
        self.assertEqual(user["premium_until"], first.premium_until)
        incidents = await self.db.get_recent_incidents_for_user(1)
        promo_incidents = [row for row in incidents if row["type"] == "promo"]
        self.assertEqual(len(promo_incidents), 1)

    async def test_connect_applies_legacy_schema_migrations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "legacy.db"
            legacy_conn = sqlite3.connect(db_path)
            legacy_conn.executescript(
                """
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    state TEXT NOT NULL,
    is_banned INTEGER NOT NULL DEFAULT 0,
    rating INTEGER NOT NULL DEFAULT 0,
    chats_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER NOT NULL,
    reported_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""
            )
            legacy_conn.commit()
            legacy_conn.close()

            migrated_db = Database(str(db_path))
            await migrated_db.connect()
            try:
                user_columns = {
                    row["name"] for row in await migrated_db.fetchall("PRAGMA table_info(users)")
                }
                report_columns = {
                    row["name"] for row in await migrated_db.fetchall("PRAGMA table_info(reports)")
                }
                migration_versions = [
                    row["version"]
                    for row in await migrated_db.fetchall(
                        "SELECT version FROM schema_migrations ORDER BY version"
                    )
                ]

                self.assertIn("username", user_columns)
                self.assertIn("last_name", user_columns)
                self.assertIn("lang", user_columns)
                self.assertIn("status", report_columns)
                self.assertIn("resolved_at", report_columns)
                self.assertIn("resolved_by", report_columns)
                self.assertEqual(migration_versions, ["0001", "0002", "0003"])
            finally:
                await migrated_db.close()

    async def test_relay_message_respects_partner_content_filter(self) -> None:
        await self._create_human_pair()
        await self.db.set_content_filter(2, True)

        bot = FakeBot()
        message = FakeMessage(1, bot, "send nudes please")

        await relay_message(message, self.db, self.config)

        self.assertEqual(bot.sent_messages, [])
        self.assertTrue(message.answers)
        self.assertTrue(
            "blocked" in message.answers[-1].lower()
            or "заблок" in message.answers[-1].lower()
        )
