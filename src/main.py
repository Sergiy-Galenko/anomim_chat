import asyncio
import logging
import sys
import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message=r'.*model_custom_emoji_id.*UniqueGiftColors.*protected namespace "model_".*',
    category=UserWarning,
)

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp_socks import ProxyConnectionError, ProxyError, ProxyTimeoutError

if __name__ == "__main__" and __package__ in (None, ""):
    # Allow running as a script: `python src/main.py`
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    __package__ = "src"

from .config import load_config
from .db.database import Database
from .bot.routers import admin, chat, interests, match, premium, profile, reports, start


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    config = load_config()
    db = Database(config.db_path)
    await db.connect()

    try:
        session = AiohttpSession(
            proxy=config.telegram_proxy,
            timeout=config.telegram_timeout_sec,
        )
    except RuntimeError as exc:
        # aiogram raises RuntimeError when TELEGRAM_PROXY is set but aiohttp-socks is missing.
        logging.error("%s", exc)
        logging.error("Install dependencies from requirements.txt and restart.")
        raise SystemExit(1) from exc
    bot = Bot(token=config.token, session=session)
    dp = Dispatcher(storage=MemoryStorage())

    # Dependencies for handlers.
    dp["db"] = db
    dp["config"] = config

    # Register routers in order of priority.
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(profile.router)
    dp.include_router(premium.router)
    dp.include_router(interests.router)
    dp.include_router(match.router)
    dp.include_router(reports.router)
    dp.include_router(chat.router)

    try:
        await dp.start_polling(bot)
    except (TelegramNetworkError, ProxyError, ProxyConnectionError, ProxyTimeoutError) as exc:
        logging.error("Failed to connect to Telegram API: %s", exc)
        if config.telegram_proxy:
            logging.error(
                "Current TELEGRAM_PROXY=%s. Check that it is reachable and valid.",
                config.telegram_proxy,
            )
        else:
            logging.error(
                "Set TELEGRAM_PROXY in .env (example: socks5://user:pass@host:1080) "
                "if your network blocks api.telegram.org."
            )
        raise SystemExit(1) from exc
    finally:
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
