from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from ...config import Config
from ...db.database import Database
from ..keyboards.main_menu import main_menu_keyboard
from ..keyboards.report_menu import REPORT_REASONS, report_keyboard
from ..utils.chat import end_chat, get_partner
from ..utils.constants import STATE_CHATTING
from ..utils.users import ensure_user, get_state, is_banned

router = Router()


class ReportStates(StatesGroup):
    waiting_reason = State()


@router.message(F.text == "🚨 Поскаржитись")
async def start_report(message: Message, db: Database, state: FSMContext) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)

    if await is_banned(db, user_id):
        return

    if await get_state(db, user_id) != STATE_CHATTING:
        await message.answer("Скарга доступна лише під час діалогу.", reply_markup=main_menu_keyboard())
        return

    await state.set_state(ReportStates.waiting_reason)
    await message.answer("Оберіть причину скарги:", reply_markup=report_keyboard())


@router.message(ReportStates.waiting_reason)
async def handle_report_reason(
    message: Message, db: Database, state: FSMContext, config: Config
) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)

    reason = (message.text or "").strip()
    if reason not in REPORT_REASONS:
        await message.answer("Будь ласка, оберіть причину з кнопок.")
        return

    partner_id, _ = await get_partner(db, user_id)
    if not partner_id:
        await state.clear()
        await message.answer("Діалог уже завершено.", reply_markup=main_menu_keyboard())
        return

    await db.add_report(user_id, partner_id, reason)
    await db.add_incident(user_id, partner_id, "report", reason)

    if config.admin_ids:
        created_at = datetime.now(timezone.utc).isoformat()
        text = (
            "🚨 Нова скарга\n"
            f"Від: {user_id}\n"
            f"На: {partner_id}\n"
            f"Причина: {reason}\n"
            f"Дата: {created_at}"
        )
        for admin_id in config.admin_ids:
            await message.bot.send_message(admin_id, text)

    await state.clear()
    await end_chat(db, message.bot, user_id)
