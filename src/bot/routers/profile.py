from aiogram import F, Router
from aiogram.types import Message

from ...config import Config
from ...db.database import Database
from ..keyboards.main_menu import main_menu_keyboard
from ..utils.constants import RULES_TEXT, STATE_CHATTING
from ..utils.admin import is_admin
from ..utils.users import ensure_user, get_state, is_banned

router = Router()


@router.message(F.text == "🧑‍💻 Мій профіль")
async def my_profile(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)

    if await is_banned(db, user_id):
        await message.answer("Ваш акаунт заблоковано адміністрацією.")
        return

    user = await db.get_user(user_id)
    state = await get_state(db, user_id)

    text = (
        "Ваш профіль:\n"
        f"ID: {user_id}\n"
        f"Дата реєстрації: {user['created_at']}\n"
        f"Чатів: {user['chats_count']}\n"
        f"Рейтинг: {user['rating']}\n"
        f"Інтерес: {user['interests'] or '—'}"
    )
    await message.answer(
        text,
        reply_markup=main_menu_keyboard(
            show_end=state == STATE_CHATTING, is_admin=is_admin(user_id, config)
        ),
    )


@router.message(F.text == "⚙️ Налаштування")
async def settings(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)

    if await is_banned(db, user_id):
        return

    state = await get_state(db, user_id)
    await message.answer(
        "Налаштування ще не доступні.",
        reply_markup=main_menu_keyboard(
            show_end=state == STATE_CHATTING, is_admin=is_admin(user_id, config)
        ),
    )


@router.message(F.text == "❓ Правила")
async def rules(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)

    if await is_banned(db, user_id):
        return

    state = await get_state(db, user_id)
    await message.answer(
        RULES_TEXT,
        reply_markup=main_menu_keyboard(
            show_end=state == STATE_CHATTING, is_admin=is_admin(user_id, config)
        ),
    )
