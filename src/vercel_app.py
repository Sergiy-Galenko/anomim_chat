import json
import logging
import secrets
from typing import Any

from aiogram.methods import TelegramMethod
from fastapi import FastAPI, Header, HTTPException, Request, Response

from .bootstrap import AppContext, get_app_context

logger = logging.getLogger(__name__)

app = FastAPI()


async def _load_context() -> AppContext:
    try:
        return await get_app_context()
    except RuntimeError as exc:
        logger.exception("Vercel bot configuration is invalid")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to initialize bot context")
        raise HTTPException(status_code=500, detail="Failed to initialize bot") from exc


async def _healthcheck() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "ghostchat-bot",
        "mode": "webhook",
    }


async def _healthcheck_head() -> Response:
    return Response(status_code=200)


async def _telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, Any]:
    ctx = await _load_context()

    if ctx.config.telegram_webhook_secret and not secrets.compare_digest(
        x_telegram_bot_api_secret_token or "",
        ctx.config.telegram_webhook_secret,
    ):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON") from None

    try:
        result = await ctx.dp.feed_webhook_update(ctx.bot, payload)
        if isinstance(result, TelegramMethod):
            await ctx.dp.silent_call_request(bot=ctx.bot, result=result)
    except Exception as exc:
        logger.exception("Failed to process Telegram webhook update")
        raise HTTPException(status_code=500, detail="Webhook processing failed") from exc

    return {"ok": True}


@app.get("/")
async def healthcheck_root() -> dict[str, Any]:
    return await _healthcheck()


@app.get("/api")
async def healthcheck_api() -> dict[str, Any]:
    return await _healthcheck()


@app.head("/")
async def healthcheck_head_root() -> Response:
    return await _healthcheck_head()


@app.head("/api")
async def healthcheck_head_api() -> Response:
    return await _healthcheck_head()


@app.post("/")
async def telegram_webhook_root(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, Any]:
    return await _telegram_webhook(request, x_telegram_bot_api_secret_token)


@app.post("/api")
async def telegram_webhook_api(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, Any]:
    return await _telegram_webhook(request, x_telegram_bot_api_secret_token)
