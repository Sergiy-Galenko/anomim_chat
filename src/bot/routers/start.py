from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from ...config import Config
from ...db.database import Database
from ..keyboards.main_menu import main_menu_keyboard
from ..utils.constants import STATE_CHATTING
from ..utils.admin import is_admin
from ..utils.i18n import button_variants, tr
from ..utils.users import (
    ensure_user,
    get_lang_from_snapshot,
    get_state_from_snapshot,
    get_user_snapshot,
    is_banned_from_snapshot,
)

router = Router()


async def _send_main_menu(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)
    user = await get_user_snapshot(db, user_id)
    lang = get_lang_from_snapshot(user)

    if is_banned_from_snapshot(user):
        await message.answer(
            tr(
                lang,
                "Ваш аккаунт заблокирован администрацией.",
                "Your account is blocked by administration.",
                "Ваш акаунт заблоковано адміністрацією.",
                "Dein Konto wurde von der Administration gesperrt.",
            )
        )
        return

    state = get_state_from_snapshot(user)
    show_end = state == STATE_CHATTING

    await message.answer(
        tr(
            lang,
            "Добро пожаловать! Это ghostchat_bot — анонимный чат. Выберите действие в меню.",
            "Welcome! This is ghostchat_bot — an anonymous chat. Choose an action from the menu.",
            "Ласкаво просимо! Це ghostchat_bot — анонімний чат. Оберіть дію в меню.",
            "Willkommen! Das ist ghostchat_bot, ein anonymer Chat. Wähle eine Aktion im Menü.",
        ),
        reply_markup=main_menu_keyboard(
            show_end=show_end,
            is_admin=is_admin(user_id, config),
            lang=lang,
        ),
    )


@router.message(CommandStart())
async def start_handler(message: Message, db: Database, config: Config) -> None:
    await _send_main_menu(message, db, config)


@router.message(F.text.in_(button_variants("menu")))
async def menu_handler(message: Message, db: Database, config: Config) -> None:
    await _send_main_menu(message, db, config)
