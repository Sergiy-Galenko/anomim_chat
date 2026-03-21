import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage

from .bot.middlewares.user_context import UserContextMiddleware
from .bot.routers import admin, chat, interests, match, premium, profile, reports, start
from .config import Config, load_config
from .db.database import Database


class ProxyConfigurationError(RuntimeError):
    pass


@dataclass(slots=True)
class AppContext:
    config: Config
    db: Database
    bot: Bot
    dp: Dispatcher


_cached_context: AppContext | None = None
_context_lock = asyncio.Lock()


def configure_logging() -> None:
    if logging.getLogger().handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def _build_session(config: Config) -> AiohttpSession:
    try:
        return AiohttpSession(
            proxy=config.telegram_proxy,
            timeout=config.telegram_timeout_sec,
        )
    except RuntimeError as exc:
        raise ProxyConfigurationError(str(exc)) from exc


def _build_dispatcher(db: Database, config: Config) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    dp["db"] = db
    dp["config"] = config
    dp.update.outer_middleware(UserContextMiddleware(db))

    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(profile.router)
    dp.include_router(premium.router)
    dp.include_router(interests.router)
    dp.include_router(match.router)
    dp.include_router(reports.router)
    dp.include_router(chat.router)

    return dp


async def create_app_context(config: Config | None = None) -> AppContext:
    configure_logging()
    config = config or load_config()

    db = Database(config.db_path)
    await db.connect()

    session = None
    try:
        session = _build_session(config)
        bot = Bot(token=config.token, session=session)
        dp = _build_dispatcher(db=db, config=config)
        return AppContext(config=config, db=db, bot=bot, dp=dp)
    except Exception:
        if session is not None:
            await session.close()
        await db.close()
        raise


async def get_app_context() -> AppContext:
    global _cached_context

    if _cached_context is not None:
        return _cached_context

    async with _context_lock:
        if _cached_context is None:
            _cached_context = await create_app_context()
        return _cached_context


async def shutdown_app_context(context: AppContext | None = None, reset_cached: bool = False) -> None:
    global _cached_context

    target = context or _cached_context
    if target is None:
        return

    if reset_cached and target is _cached_context:
        _cached_context = None

    await target.db.close()
    await target.bot.session.close()
