import asyncio
import unittest

from src.db.database import Database


class MatchLoadTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = Database(":memory:")
        await self.db.connect()

    async def asyncTearDown(self) -> None:
        await self.db.close()

    async def test_parallel_match_and_close_roundtrip(self) -> None:
        user_ids = list(range(1, 41))
        await asyncio.gather(*(self.db.create_user_if_missing(user_id) for user_id in user_ids))
        await asyncio.gather(*(self.db.queue_user_for_search(user_id) for user_id in user_ids))

        match_tasks = [
            self.db.finalize_match(user1_id, user1_id + 1, is_virtual=False)
            for user1_id in range(1, 41, 2)
        ]
        match_results = await asyncio.gather(*match_tasks)
        self.assertTrue(all(match_results))

        close_tasks = [
            self.db.end_chat_session(user1_id, collect_feedback=False)
            for user1_id in range(1, 41, 2)
        ]
        close_results = await asyncio.gather(*close_tasks)
        self.assertTrue(all(close_results))

        self.assertEqual(await self.db.get_active_user_ids(), [])
