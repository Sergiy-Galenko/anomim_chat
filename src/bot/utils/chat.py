from typing import Optional, Tuple

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message

from ...db.database import Database
from ..keyboards.match_menu import find_new_keyboard
from ..keyboards.rating_menu import rating_keyboard
from .i18n import tr


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


def _is_not_modified_error(exc: TelegramBadRequest) -> bool:
    return "message is not modified" in str(exc).lower()


async def safe_edit_message_text(message: Message, text: str, reply_markup=None, **kwargs) -> bool:
    try:
        await message.edit_text(text, reply_markup=reply_markup, **kwargs)
        return True
    except TelegramBadRequest as exc:
        if _is_not_modified_error(exc):
            return False
        raise


async def safe_edit_message_reply_markup(message: Message, reply_markup=None) -> bool:
    try:
        await message.edit_reply_markup(reply_markup=reply_markup)
        return True
    except TelegramBadRequest as exc:
        if _is_not_modified_error(exc):
            return False
        raise


async def end_chat(
    db: Database,
    bot: Bot,
    user_id: int,
    notify_partner: bool = True,
    notify_user: bool = True,
    collect_feedback: bool = True,
    reason_ru: str = "❌ Диалог завершен.",
    reason_en: str = "❌ Chat ended.",
    reason_uk: str | None = None,
    reason_de: str | None = None,
) -> Optional[int]:
    result = await db.end_chat_session(
        user_id,
        notify_partner=notify_partner,
        notify_user=notify_user,
        collect_feedback=collect_feedback,
        ended_by_user=True,
    )
    if result is None:
        return None
    partner_id = result.partner_id
    partner_is_virtual = result.partner_is_virtual

    if notify_user:
        user_lang = await db.get_lang(user_id)
        await safe_send_message(
            bot,
            user_id,
            tr(user_lang, reason_ru, reason_en, reason_uk, reason_de),
            reply_markup=find_new_keyboard(user_lang),
        )
        if result.user_feedback_pending:
            await safe_send_message(
                bot,
                user_id,
                tr(
                    user_lang,
                    "Оцените собеседника:",
                    "Rate your partner:",
                    "Оцініть співрозмовника:",
                    "Bewerte deinen Gesprächspartner:",
                ),
                reply_markup=rating_keyboard(),
            )
    if notify_partner and not partner_is_virtual:
        partner_lang = await db.get_lang(partner_id)
        await safe_send_message(
            bot,
            partner_id,
            tr(partner_lang, reason_ru, reason_en, reason_uk, reason_de),
            reply_markup=find_new_keyboard(partner_lang),
        )
        if result.partner_feedback_pending:
            await safe_send_message(
                bot,
                partner_id,
                tr(
                    partner_lang,
                    "Оцените собеседника:",
                    "Rate your partner:",
                    "Оцініть співрозмовника:",
                    "Bewerte deinen Gesprächspartner:",
                ),
                reply_markup=rating_keyboard(),
            )

    return None if partner_is_virtual else partner_id
