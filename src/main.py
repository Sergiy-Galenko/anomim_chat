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

from aiogram.exceptions import TelegramNetworkError
from aiohttp_socks import ProxyConnectionError, ProxyError, ProxyTimeoutError

if __name__ == "__main__" and __package__ in (None, ""):
    # Allow running as a script: `python src/main.py`
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    __package__ = "src"

from .bootstrap import ProxyConfigurationError, create_app_context, shutdown_app_context


async def main() -> None:
    app = None
    try:
        app = await create_app_context()
        await app.bot.delete_webhook(drop_pending_updates=False)
        await app.dp.start_polling(app.bot)
    except ProxyConfigurationError as exc:
        logging.error("%s", exc)
        logging.error("Install dependencies from requirements.txt and restart.")
        raise SystemExit(1) from exc
    except (TelegramNetworkError, ProxyError, ProxyConnectionError, ProxyTimeoutError) as exc:
        logging.error("Failed to connect to Telegram API: %s", exc)
        if app is not None and app.config.telegram_proxy:
            logging.error(
                "Current TELEGRAM_PROXY=%s. Check that it is reachable and valid.",
                app.config.telegram_proxy,
            )
        else:
            logging.error(
                "Set TELEGRAM_PROXY in .env (example: socks5://user:pass@host:1080) "
                "if your network blocks api.telegram.org."
            )
        raise SystemExit(1) from exc
    finally:
        if app is not None:
            await shutdown_app_context(app)


if __name__ == "__main__":
    asyncio.run(main())
