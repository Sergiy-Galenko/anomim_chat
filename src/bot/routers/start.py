from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from ...config import Config
from ...db.database import Database
from ..keyboards.main_menu import main_menu_keyboard
from ..utils.constants import STATE_CHATTING
from ..utils.admin import is_admin
from ..utils.i18n import tr
from ..utils.users import ensure_user, get_state, is_banned

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)
    lang = await db.get_lang(user_id)

    if await is_banned(db, user_id):
        await message.answer(
            tr(
                lang,
                "Ваш аккаунт заблокирован администрацией.",
                "Your account is blocked by administration.",
            )
        )
        return

    state = await get_state(db, user_id)
    show_end = state == STATE_CHATTING

    await message.answer(
        tr(
            lang,
            "Добро пожаловать! Это ghostchat_bot — анонимный чат. Выберите действие в меню.",
            "Welcome! This is ghostchat_bot — an anonymous chat. Choose an action from the menu.",
        ),
        reply_markup=main_menu_keyboard(
            show_end=show_end,
            is_admin=is_admin(user_id, config),
            lang=lang,
        ),
    )
