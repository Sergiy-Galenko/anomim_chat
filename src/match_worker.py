import asyncio
import logging

from aiogram import Bot

from .bot.routers.match import _attempt_match
from .config import Config
from .db.database import Database

logger = logging.getLogger(__name__)
MATCH_RETRY_INTERVAL_SECONDS = 5


async def retry_pending_matches(bot: Bot, db: Database, config: Config) -> None:
    after_user_id = 0
    while user_ids := await db.get_searching_user_ids(after_user_id=after_user_id):
        for user_id in user_ids:
            try:
                await _attempt_match(bot, db, config, user_id)
            except Exception:
                logger.exception("Failed to retry matching for user %s", user_id)
        after_user_id = user_ids[-1]


async def run_match_worker(bot: Bot, db: Database, config: Config) -> None:
    # Queue timestamps live in the DB, so restarts do not reset waiting time.
    while True:
        try:
            await retry_pending_matches(bot, db, config)
        except Exception:
            logger.exception("Failed to scan the matchmaking queue")
        await asyncio.sleep(MATCH_RETRY_INTERVAL_SECONDS)
