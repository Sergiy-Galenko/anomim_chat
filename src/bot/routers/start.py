from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from ...config import Config
from ...db.database import Database
from ..keyboards.main_menu import main_menu_keyboard
from ..utils.constants import STATE_CHATTING
from ..utils.admin import is_admin
from ..utils.users import ensure_user, get_state, is_banned

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)

    if await is_banned(db, user_id):
        await message.answer("Ваш акаунт заблоковано адміністрацією.")
        return

    state = await get_state(db, user_id)
    show_end = state == STATE_CHATTING

    await message.answer(
        "Вітаю! Це ghostchat_bot — анонімний чат. Оберіть дію з меню.",
        reply_markup=main_menu_keyboard(show_end=show_end, is_admin=is_admin(user_id, config)),
    )
