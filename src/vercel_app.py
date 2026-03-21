import json
import logging
import secrets
from typing import Any, Awaitable, Callable

from aiogram.methods import TelegramMethod

from .bootstrap import get_app_context

ASGIReceive = Callable[[], Awaitable[dict[str, Any]]]
ASGISend = Callable[[dict[str, Any]], Awaitable[None]]

logger = logging.getLogger(__name__)


def _headers(scope: dict[str, Any]) -> dict[str, str]:
    return {
        key.decode("latin-1").lower(): value.decode("latin-1")
        for key, value in scope.get("headers", [])
    }


async def _read_body(receive: ASGIReceive) -> bytes:
    body = bytearray()
    while True:
        message = await receive()
        if message["type"] != "http.request":
            continue
        body.extend(message.get("body", b""))
        if not message.get("more_body", False):
            return bytes(body)


async def _send_response(
    send: ASGISend,
    status: int,
    body: bytes,
    content_type: bytes = b"application/json; charset=utf-8",
) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", content_type),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def _send_json(send: ASGISend, status: int, payload: dict[str, Any]) -> None:
    await _send_response(send, status, json.dumps(payload).encode("utf-8"))


async def app(scope: dict[str, Any], receive: ASGIReceive, send: ASGISend) -> None:
    if scope["type"] != "http":
        await _send_response(send, 404, b"Not found", content_type=b"text/plain; charset=utf-8")
        return

    method = scope.get("method", "GET").upper()
    if method in {"GET", "HEAD"}:
        body = b""
        if method == "GET":
            body = json.dumps(
                {
                    "ok": True,
                    "service": "ghostchat-bot",
                    "mode": "webhook",
                }
            ).encode("utf-8")
        await _send_response(send, 200, body)
        return

    if method != "POST":
        await _send_json(send, 405, {"ok": False, "error": "Method not allowed"})
        return

    ctx = await get_app_context()
    telegram_secret = _headers(scope).get("x-telegram-bot-api-secret-token", "")
    if ctx.config.telegram_webhook_secret and not secrets.compare_digest(
        telegram_secret, ctx.config.telegram_webhook_secret
    ):
        await _send_json(send, 401, {"ok": False, "error": "Unauthorized"})
        return

    try:
        raw_body = await _read_body(receive)
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        await _send_json(send, 400, {"ok": False, "error": "Invalid JSON"})
        return

    try:
        result = await ctx.dp.feed_webhook_update(ctx.bot, payload)
        if isinstance(result, TelegramMethod):
            await ctx.dp.silent_call_request(bot=ctx.bot, result=result)
    except Exception:
        logger.exception("Failed to process Telegram webhook update")
        await _send_json(send, 500, {"ok": False, "error": "Webhook processing failed"})
        return

    await _send_json(send, 200, {"ok": True})
