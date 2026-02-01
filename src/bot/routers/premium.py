from aiogram import F, Router
from aiogram.types import Message

from ...config import Config
from ...db.database import Database
from ..keyboards.main_menu import main_menu_keyboard
from ..utils.admin import is_admin
from ..utils.constants import PREMIUM_INFO_TEXT, STATE_CHATTING
from ..utils.users import ensure_user, get_state, is_banned

router = Router()


@router.message(F.text == "⭐ Premium")
async def premium_info(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)

    if await is_banned(db, user_id):
        return

    state = await get_state(db, user_id)
    await message.answer(
        PREMIUM_INFO_TEXT,
        reply_markup=main_menu_keyboard(show_end=state == STATE_CHATTING, is_admin=is_admin(user_id, config)),
    )
