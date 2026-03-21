import json
import logging
import secrets
from typing import Any

from aiogram.methods import TelegramMethod
from fastapi import FastAPI, Header, HTTPException, Request, Response

from .bootstrap import get_app_context

logger = logging.getLogger(__name__)

app = FastAPI()


@app.get("/")
async def healthcheck() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "ghostchat-bot",
        "mode": "webhook",
    }


@app.head("/")
async def healthcheck_head() -> Response:
    return Response(status_code=200)


@app.post("/")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, Any]:
    ctx = await get_app_context()

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
