from typing import Optional, Tuple

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from ...db.database import Database
from .constants import STATE_IDLE
from ..keyboards.main_menu import main_menu_keyboard
from ..keyboards.match_menu import find_new_keyboard


async def get_partner(db: Database, user_id: int) -> Tuple[Optional[int], Optional[int]]:
    pair = await db.get_active_pair(user_id)
    if not pair:
        return None, None
    partner_id = pair["user2_id"] if pair["user1_id"] == user_id else pair["user1_id"]
    return int(partner_id), int(pair["id"])


async def safe_send_message(bot: Bot, user_id: int, text: str, reply_markup=None) -> bool:
    try:
        await bot.send_message(user_id, text, reply_markup=reply_markup)
        return True
    except (TelegramForbiddenError, TelegramBadRequest):
        return False


async def end_chat(
    db: Database,
    bot: Bot,
    user_id: int,
    notify_partner: bool = True,
    notify_user: bool = True,
    reason_text: str = "❌ Діалог завершено.",
) -> Optional[int]:
    partner_id, pair_id = await get_partner(db, user_id)
    if not pair_id or not partner_id:
        return None

    await db.end_pair(pair_id)
    await db.set_state(user_id, STATE_IDLE)
    await db.set_state(partner_id, STATE_IDLE)

    if notify_user:
        await safe_send_message(bot, user_id, reason_text, reply_markup=find_new_keyboard())
    if notify_partner:
        await safe_send_message(bot, partner_id, reason_text, reply_markup=find_new_keyboard())

    return partner_id
