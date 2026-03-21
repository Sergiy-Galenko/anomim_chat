from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from ...db.database import Database


class UserContextMiddleware(BaseMiddleware):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = self._resolve_user(event, data)
        if user is not None:
            await self.db.create_user_if_missing(user.id)
            await self.db.update_user_profile(
                user_id=user.id,
                username=user.username or "",
                first_name=user.first_name or "",
                last_name=user.last_name or "",
            )

        return await handler(event, data)

    def _resolve_user(self, event: TelegramObject, data: Dict[str, Any]) -> User | None:
        user = data.get("event_from_user")
        if user is not None:
            return user

        direct_user = getattr(event, "from_user", None)
        if direct_user is not None:
            return direct_user

        for attr_name in (
            "message",
            "edited_message",
            "callback_query",
            "inline_query",
            "chosen_inline_result",
            "shipping_query",
            "pre_checkout_query",
            "my_chat_member",
            "chat_member",
            "chat_join_request",
            "business_message",
            "edited_business_message",
            "purchased_paid_media",
        ):
            nested_event = getattr(event, attr_name, None)
            nested_user = getattr(nested_event, "from_user", None)
            if nested_user is not None:
                return nested_user

        return None
