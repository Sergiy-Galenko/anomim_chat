import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Chat, Message, Update, User

from src.bot.keyboards.rating_menu import rating_keyboard
from src.bot.middlewares.user_context import UserContextMiddleware
from src.bot.routers.chat import rate_partner, relay_message
from src.bot.routers.match import _attempt_match, find_partner
from src.bot.routers.premium import successful_payment
from src.bot.routers.reports import handle_report_reason, start_report
from src.db.database import Database
from src.match_worker import retry_pending_matches, run_match_worker


def fake_message(user_id=1, text="hello", chat_type="private"):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=user_id, username="tester", first_name="Tester", last_name=""),
        chat=SimpleNamespace(id=user_id if chat_type == "private" else -100123, type=chat_type),
        text=text, message_id=1, answer=AsyncMock(),
        bot=SimpleNamespace(send_message=AsyncMock()),
        photo=None, video=None, animation=None, audio=None, voice=None,
        video_note=None, sticker=None, document=None, caption=None,
    )


class RegressionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = Database(":memory:")
        await self.db.connect()
        self.addAsyncCleanup(self.db.close)
        for user_id in (1, 2, 3):
            await self.db.create_user_if_missing(user_id)
        self.config = SimpleNamespace(admin_ids=[])
        self.message = fake_message()

    async def test_rollback_is_not_committed_by_parallel_write(self):
        with self.assertRaises(RuntimeError):
            async with self.db.transaction() as connection:
                await self.db.execute(
                    "UPDATE users SET rating = 999 WHERE user_id = 1",
                    connection=connection, commit=False,
                )
                writer = asyncio.create_task(self.db.set_lang(2, "en"))
                reader = asyncio.create_task(self.db.get_user(1))
                await asyncio.sleep(0.02)
                self.assertFalse(writer.done())
                self.assertFalse(reader.done())
                raise RuntimeError("abort")
        await asyncio.wait_for(writer, timeout=2)
        self.assertEqual((await reader)["rating"], 0)
        self.assertEqual((await self.db.get_user(2))["lang"], "en")

    async def test_exception_rolls_back_and_connection_remains_usable(self):
        with self.assertRaises(RuntimeError):
            async with self.db.transaction() as connection:
                await self.db.execute(
                    "UPDATE users SET rating = 999 WHERE user_id = 1",
                    connection=connection, commit=False,
                )
                raise RuntimeError("abort")
        self.assertEqual((await self.db.get_user(1))["rating"], 0)
        await self.db.queue_user_for_search(1)
        self.assertEqual(await self.db.get_queue_size(), 1)

    async def test_cancelled_transaction_rolls_back(self):
        ready = asyncio.Event()

        async def transaction():
            async with self.db.transaction() as connection:
                await self.db.execute(
                    "UPDATE users SET rating = 999 WHERE user_id = 1",
                    connection=connection, commit=False,
                )
                ready.set()
                await asyncio.Event().wait()

        task = asyncio.create_task(transaction())
        await asyncio.wait_for(ready.wait(), timeout=2)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual((await self.db.get_user(1))["rating"], 0)
        self.assertTrue(await self.db.queue_user_for_search(1))

    async def test_payment_retry_after_notification_failure_grants_once(self):
        self.message.successful_payment = SimpleNamespace(
            invoice_payload="premium_7", total_amount=29, currency="XTR",
            telegram_payment_charge_id="same-charge",
        )
        self.message.answer.side_effect = RuntimeError("notification failed")
        with self.assertRaises(RuntimeError):
            await successful_payment(self.message, self.db)
        first = await self.db.get_premium_until(1)
        self.message.answer.side_effect = None
        await successful_payment(self.message, self.db)
        self.assertEqual(await self.db.get_premium_until(1), first)
        self.assertEqual((await self.db.fetchone("SELECT COUNT(*) AS n FROM payments"))["n"], 1)
        self.assertEqual((await self.db.fetchone("SELECT COUNT(*) AS n FROM incidents WHERE type = 'payment'"))["n"], 1)

    async def test_distinct_payments_extend_but_same_charge_does_not(self):
        first = await self.db.grant_paid_premium(1, 7, "premium_7|29|XTR", charge_id="first")
        results = await asyncio.gather(
            self.db.grant_paid_premium(1, 7, "premium_7|29|XTR", charge_id="second"),
            self.db.grant_paid_premium(1, 7, "premium_7|29|XTR", charge_id="second"),
        )
        self.assertEqual(results[0], results[1])
        self.assertEqual(datetime.fromisoformat(results[0]) - datetime.fromisoformat(first), timedelta(days=7))

    async def test_payment_failure_rolls_back_ledger_and_entitlement(self):
        execute = self.db.execute

        async def fail_incident(query, *args, **kwargs):
            if "INSERT INTO incidents" in query:
                raise RuntimeError("failed audit insert")
            return await execute(query, *args, **kwargs)

        with patch.object(self.db, "execute", side_effect=fail_incident):
            with self.assertRaises(RuntimeError):
                await self.db.grant_paid_premium(1, 7, "payload", charge_id="retry-me")
        self.assertEqual(await self.db.get_premium_until(1), "")
        self.assertEqual((await self.db.fetchone("SELECT COUNT(*) AS n FROM payments"))["n"], 0)
        await self.db.grant_paid_premium(1, 7, "payload", charge_id="retry-me")
        self.assertTrue(await self.db.get_premium_until(1))

    async def test_old_rating_buttons_cannot_rate_a_new_chat(self):
        old_pair = await self.db.start_human_pair(1, 2)
        await self.db.end_chat_session(1)
        current_pair = await self.db.start_human_pair(1, 3)
        await self.db.end_chat_session(1)
        callback = SimpleNamespace(
            from_user=SimpleNamespace(id=1), answer=AsyncMock(),
            message=SimpleNamespace(edit_reply_markup=AsyncMock(), answer=AsyncMock()),
        )
        for data in (f"rate:{old_pair}:down", "rate:down", "rate:garbage:up"):
            callback.data = data
            await rate_partner(callback, self.db)
            self.assertEqual((await self.db.get_user(3))["rating"], 0)
            self.assertEqual(await self.db.get_pending_rating(1), (current_pair, 3))
        callback.data = rating_keyboard(current_pair).inline_keyboard[0][1].callback_data
        await rate_partner(callback, self.db)
        await rate_partner(callback, self.db)
        self.assertEqual((await self.db.get_user(2))["rating"], 0)
        self.assertEqual((await self.db.get_user(3))["rating"], -1)

    def make_state(self):
        return FSMContext(MemoryStorage(), StorageKey(bot_id=99, chat_id=1, user_id=1))

    async def test_stale_report_keeps_new_partner_and_chat_untouched(self):
        state = self.make_state()
        await self.db.start_human_pair(1, 2)
        await start_report(self.message, self.db, state, self.config)
        await self.db.end_chat_session(2)
        new_pair = await self.db.start_human_pair(1, 3)
        self.message.text = "spam"
        await handle_report_reason(self.message, self.db, state, self.config)
        self.assertIsNone(await self.db.get_next_report())
        self.assertEqual((await self.db.get_active_pair(1))["id"], new_pair)
        self.assertIsNone(await state.get_state())

    async def test_report_checks_pair_inside_transaction(self):
        old_pair = await self.db.start_human_pair(1, 2)
        await self.db.end_chat_session(2)
        new_pair = await self.db.start_human_pair(1, 2)
        result = await self.db.report_chat_session(
            1, "spam", expected_pair_id=old_pair, expected_partner_id=2,
        )
        self.assertIsNone(result)
        self.assertEqual((await self.db.get_active_pair(1))["id"], new_pair)
        self.assertIsNone(await self.db.get_next_report())

    async def test_current_report_still_works(self):
        state = self.make_state()
        await self.db.start_human_pair(1, 2)
        await start_report(self.message, self.db, state, self.config)
        self.message.text = "spam"
        await handle_report_reason(self.message, self.db, state, self.config)
        self.assertEqual((await self.db.get_next_report())["reported_id"], 2)
        self.assertIsNone(await self.db.get_active_pair(1))
        self.assertIsNone(await state.get_state())

    async def test_group_message_is_not_relayed_but_private_message_is(self):
        await self.db.start_human_pair(1, 2)
        for chat_type in ("group", "supergroup", "channel"):
            message = fake_message(chat_type=chat_type)
            await relay_message(message, self.db, self.config)
            message.bot.send_message.assert_not_awaited()
        await relay_message(self.message, self.db, self.config)
        self.message.bot.send_message.assert_awaited_once_with(2, "hello")

    async def test_group_update_is_blocked_before_handlers_and_user_context(self):
        db = SimpleNamespace(touch_user_context=AsyncMock())
        middleware = UserContextMiddleware(db)
        handler = AsyncMock()
        event = Update(update_id=1, message=Message(
            message_id=1, date=datetime.now(timezone.utc), text="/start",
            from_user=User(id=1, first_name="Tester", is_bot=False),
            chat=Chat(id=-100123, type="supergroup"),
        ))
        await middleware(handler, event, {})
        handler.assert_not_awaited()
        db.touch_user_context.assert_not_awaited()

    async def prepare_search(self, aged=True):
        await self.db.set_virtual_bot_enabled_count(0)
        await self.db.set_interests(1, "music")
        await self.db.set_interests(2, "sports")
        for user_id in (1, 2):
            await self.db.queue_user_for_search(user_id)
        self.assertFalse(await _attempt_match(self.message.bot, self.db, self.config, 1))
        if aged:
            old = (datetime.now(timezone.utc) - timedelta(seconds=90)).isoformat()
            await self.db.execute("UPDATE queue SET joined_at = ?", (old,))

    async def test_search_button_retries_matching_after_soft_expansion(self):
        await self.prepare_search()
        await find_partner(self.message, self.db, self.config)
        self.assertIsNotNone(await self.db.get_active_pair(1))
        self.assertEqual(await self.db.get_queue_size(), 0)

    async def test_worker_matches_without_new_messages(self):
        await self.prepare_search()
        await retry_pending_matches(self.message.bot, self.db, self.config)
        self.assertIsNotNone(await self.db.get_active_pair(1))
        self.assertEqual(self.message.bot.send_message.await_count, 2)
        await retry_pending_matches(self.message.bot, self.db, self.config)
        self.assertEqual(self.message.bot.send_message.await_count, 2)

    async def test_worker_respects_interest_only_and_cancelled_search(self):
        await self.prepare_search()
        await self.db.set_premium_until(1, (datetime.now(timezone.utc) + timedelta(days=1)).isoformat())
        await self.db.set_only_interest(1, True)
        await retry_pending_matches(self.message.bot, self.db, self.config)
        self.assertIsNone(await self.db.get_active_pair(1))
        await self.db.set_only_interest(1, False)
        await self.db.cancel_search(1)
        await retry_pending_matches(self.message.bot, self.db, self.config)
        self.assertIsNone(await self.db.get_active_pair(1))

    async def test_queue_cannot_overwrite_active_chat_or_reset_wait_time(self):
        await self.db.queue_user_for_search(1)
        joined = await self.db.get_queue_joined_at(1)
        self.assertFalse(await self.db.queue_user_for_search(1))
        self.assertEqual(await self.db.get_queue_joined_at(1), joined)
        await self.db.queue_user_for_search(2)
        await self.db.finalize_match(1, 2, is_virtual=False)
        self.assertFalse(await self.db.queue_user_for_search(1))
        self.assertEqual((await self.db.get_user(1))["state"], "chatting")
        self.assertEqual(await self.db.get_queue_size(), 0)

    async def test_worker_repeats_and_can_be_cancelled(self):
        second_pass = asyncio.Event()
        calls = 0

        async def sweep(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                second_pass.set()

        with patch("src.match_worker.retry_pending_matches", side_effect=sweep), patch("src.match_worker.MATCH_RETRY_INTERVAL_SECONDS", 0.01):
            task = asyncio.create_task(run_match_worker(self.message.bot, self.db, self.config))
            try:
                await asyncio.wait_for(second_pass.wait(), timeout=2)
            finally:
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task

    async def test_competing_sqlite_connections_create_only_one_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "isolated.db")
            first, second = Database(path), Database(path)
            await first.connect()
            await second.connect()
            try:
                for user_id in (1, 2, 3):
                    await first.create_user_if_missing(user_id)
                    await first.queue_user_for_search(user_id)
                results = await asyncio.gather(
                    first.finalize_match(1, 2, is_virtual=False),
                    second.finalize_match(3, 2, is_virtual=False),
                )
                self.assertEqual(sum(result is not None for result in results), 1)
                self.assertEqual((await first.fetchone("SELECT COUNT(*) AS n FROM pairs WHERE is_active = 1"))["n"], 1)
            finally:
                await first.close()
                await second.close()


if __name__ == "__main__":
    unittest.main()
