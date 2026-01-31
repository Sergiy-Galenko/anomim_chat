import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

if __name__ == "__main__" and __package__ in (None, ""):
    # Allow running as a script: `python src/main.py`
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    __package__ = "src"

from .config import load_config
from .db.database import Database
from .bot.routers import admin, chat, interests, match, profile, reports, start


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    config = load_config()
    db = Database(config.db_path)
    await db.connect()

    bot = Bot(token=config.token)
    dp = Dispatcher(storage=MemoryStorage())

    # Dependencies for handlers.
    dp["db"] = db
    dp["config"] = config

    # Register routers in order of priority.
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(profile.router)
    dp.include_router(interests.router)
    dp.include_router(match.router)
    dp.include_router(reports.router)
    dp.include_router(chat.router)

    try:
        await dp.start_polling(bot)
    finally:
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
