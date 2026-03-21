from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from ...config import Config
from ...db.database import Database
from ..keyboards.main_menu import main_menu_keyboard
from ..keyboards.report_menu import parse_report_reason, report_keyboard, report_reason_label
from ..utils.chat import end_chat, get_partner
from ..utils.admin import is_admin
from ..utils.constants import STATE_CHATTING
from ..utils.i18n import button_variants, tr
from ..utils.users import ensure_user, get_state, is_banned
from ..utils.virtual_companions import is_virtual_companion

router = Router()


class ReportStates(StatesGroup):
    waiting_reason = State()


@router.message(F.text.in_(button_variants("report")))
async def start_report(
    message: Message, db: Database, state: FSMContext, config: Config
) -> None:
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

    if await get_state(db, user_id) != STATE_CHATTING:
        await message.answer(
            tr(
                lang,
                "Жалоба доступна только во время диалога.",
                "Report is available only during an active chat.",
            ),
            reply_markup=main_menu_keyboard(
                is_admin=is_admin(user_id, config),
                lang=lang,
            ),
        )
        return

    partner_id, _ = await get_partner(db, user_id)
    if partner_id and is_virtual_companion(partner_id):
        await message.answer(
            tr(
                lang,
                "На встроенную виртуальную собеседницу жалобу отправить нельзя.",
                "You can't send a report on the built-in virtual companion.",
            ),
            reply_markup=main_menu_keyboard(
                show_end=True,
                is_admin=is_admin(user_id, config),
                lang=lang,
            ),
        )
        return

    await state.set_state(ReportStates.waiting_reason)
    await state.update_data(lang=lang)
    await message.answer(
        tr(lang, "Выберите причину жалобы:", "Choose a report reason:"),
        reply_markup=report_keyboard(lang),
    )


@router.message(ReportStates.waiting_reason)
async def handle_report_reason(
    message: Message, db: Database, state: FSMContext, config: Config
) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)
    data = await state.get_data()
    lang = data.get("lang") or await db.get_lang(user_id)

    reason_code = parse_report_reason((message.text or "").strip())
    if not reason_code:
        await message.answer(
            tr(
                lang,
                "Пожалуйста, выберите причину кнопкой.",
                "Please choose a reason from the buttons.",
            )
        )
        return

    partner_id, _ = await get_partner(db, user_id)
    if not partner_id:
        await state.clear()
        await message.answer(
            tr(lang, "Диалог уже завершен.", "Chat already ended."),
            reply_markup=main_menu_keyboard(
                is_admin=is_admin(user_id, config),
                lang=lang,
            ),
        )
        return
    if is_virtual_companion(partner_id):
        await state.clear()
        await message.answer(
            tr(
                lang,
                "На встроенную виртуальную собеседницу жалобу отправить нельзя.",
                "You can't send a report on the built-in virtual companion.",
            ),
            reply_markup=main_menu_keyboard(
                show_end=True,
                is_admin=is_admin(user_id, config),
                lang=lang,
            ),
        )
        return

    await db.add_report(user_id, partner_id, reason_code)
    await db.add_incident(user_id, partner_id, "report", reason_code)

    if config.admin_ids:
        created_at = datetime.now(timezone.utc).isoformat()
        for admin_id in config.admin_ids:
            admin_lang = await db.get_lang(admin_id)
            text = (
                tr(admin_lang, "🚨 Новая жалоба\n", "🚨 New report\n")
                + f"{tr(admin_lang, 'От', 'From')}: {user_id}\n"
                + f"{tr(admin_lang, 'На', 'Against')}: {partner_id}\n"
                + f"{tr(admin_lang, 'Причина', 'Reason')}: {report_reason_label(reason_code, admin_lang)}\n"
                + f"{tr(admin_lang, 'Дата', 'Date')}: {created_at}"
            )
            await message.bot.send_message(admin_id, text)

    await state.clear()
    await end_chat(db, message.bot, user_id, collect_feedback=False)
