import csv
import io
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from ...config import Config
from ...db.database import Database
from ..keyboards.admin_menu import (
    admin_cancel_keyboard,
    admin_confirm_keyboard,
    admin_menu_keyboard,
    report_action_keyboard,
)
from ..keyboards.report_menu import report_reason_label
from ..utils.chat import end_chat, safe_send_message
from ..utils.constants import PREMIUM_INFO_TEXT_EN, PREMIUM_INFO_TEXT_RU, STATE_IDLE
from ..utils.i18n import button_variants, tr
from ..utils.premium import add_premium_days, is_premium_until
from ..utils.users import format_until_text

router = Router()

class AdminStates(StatesGroup):
    waiting_ban_id = State()
    confirm_ban = State()
    waiting_unban_id = State()
    confirm_unban = State()


def _is_admin(user_id: int, config: Config) -> bool:
    return user_id in config.admin_ids


def _parse_target_id(text: str) -> int | None:
    parts = text.strip().split()
    if len(parts) == 1:
        candidate = parts[0]
    elif len(parts) >= 2:
        candidate = parts[1]
    else:
        return None
    try:
        return int(candidate)
    except ValueError:
        return None


def _parse_positive_hours(text: str) -> int | None:
    try:
        value = int(text)
    except ValueError:
        return None
    if value <= 0:
        return None
    return value


def _stats_text(data: dict[str, int], lang: str) -> str:
    return (
        tr(lang, "🧰 Админ-панель\n", "🧰 Admin Panel\n")
        + "----------------\n"
        + tr(lang, "📊 Статистика\n", "📊 Statistics\n")
        + f"- {tr(lang, 'Пользователи', 'Users')}: {data['users']}\n"
        + f"- {tr(lang, 'Активные чаты', 'Active chats')}: {data['active_chats']}\n"
        + f"- {tr(lang, 'В очереди', 'In queue')}: {data['queue']}\n"
        + f"- {tr(lang, 'Жалобы', 'Reports')}: {data['reports']}\n"
        + f"- {tr(lang, 'Заблокированные', 'Blocked')}: {data['banned']}\n"
        + "\n"
        + tr(lang, "Действия доступны кнопками ниже.", "Use the buttons below.")
    )


def _display_name(chat, lang: str) -> str:
    if getattr(chat, "username", None):
        return f"@{chat.username}"
    name_parts = [chat.first_name or "", chat.last_name or ""]
    name = " ".join([p for p in name_parts if p]).strip()
    return name if name else tr(lang, "Без имени", "No name")


def _chunk_lines(lines: list[str], max_len: int = 3500) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for line in lines:
        line_len = len(line) + (1 if current else 0)
        if length + line_len > max_len and current:
            chunks.append("\n".join(current))
            current = [line]
            length = len(line)
        else:
            current.append(line)
            length += line_len
    if current:
        chunks.append("\n".join(current))
    return chunks


@router.message(Command("admin"))
async def admin_panel(message: Message, db: Database, config: Config) -> None:
    lang = await db.get_lang(message.from_user.id)
    if not _is_admin(message.from_user.id, config):
        await message.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."))
        return

    data = await db.stats()
    await message.answer(_stats_text(data, lang), reply_markup=admin_menu_keyboard(lang))


@router.message(Command("premium"))
async def premium_command(message: Message, db: Database, config: Config) -> None:
    lang = await db.get_lang(message.from_user.id)
    parts = (message.text or "").split()
    if len(parts) == 1:
        await message.answer(PREMIUM_INFO_TEXT_EN if lang == "en" else PREMIUM_INFO_TEXT_RU)
        return

    if not _is_admin(message.from_user.id, config):
        await message.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."))
        return

    if len(parts) < 3:
        await message.answer(tr(lang, "Использование: /premium <user_id> <days>", "Usage: /premium <user_id> <days>"))
        return

    try:
        target_id = int(parts[1])
        days = int(parts[2])
    except ValueError:
        await message.answer(
            tr(
                lang,
                "Неверный формат. Использование: /premium <user_id> <days>",
                "Invalid format. Usage: /premium <user_id> <days>",
            )
        )
        return

    if days <= 0:
        await message.answer(tr(lang, "Количество дней должно быть больше 0.", "Days must be greater than 0."))
        return

    current_until = await db.get_premium_until(target_id)
    new_until = add_premium_days(current_until, days)
    await db.set_premium_until(target_id, new_until)
    await message.answer(
        tr(
            lang,
            f"Premium активирован для {target_id} до {new_until}.",
            f"Premium activated for {target_id} until {new_until}.",
        )
    )
    await db.add_incident(message.from_user.id, target_id, "premium_grant", f"{days}d")


@router.message(Command("premium_clear"))
async def premium_clear(message: Message, db: Database, config: Config) -> None:
    lang = await db.get_lang(message.from_user.id)
    if not _is_admin(message.from_user.id, config):
        await message.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."))
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer(tr(lang, "Использование: /premium_clear <user_id>", "Usage: /premium_clear <user_id>"))
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer(tr(lang, "Неверный формат user_id.", "Invalid user_id format."))
        return

    await db.set_premium_until(target_id, "")
    await message.answer(
        tr(
            lang,
            f"Premium для {target_id} отключен.",
            f"Premium disabled for {target_id}.",
        )
    )
    await db.add_incident(message.from_user.id, target_id, "premium_clear", "")


@router.message(F.text.in_(button_variants("admin_panel")))
async def admin_panel_button(message: Message, db: Database, config: Config) -> None:
    await admin_panel(message, db, config)


@router.callback_query(F.data == "admin:close")
async def admin_close(callback: CallbackQuery, db: Database, config: Config) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()


@router.callback_query(F.data.in_({"admin:stats", "admin:refresh"}))
async def admin_stats(callback: CallbackQuery, db: Database, config: Config) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    data = await db.stats()
    await callback.message.edit_text(_stats_text(data, lang), reply_markup=admin_menu_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data == "admin:export_stats")
async def admin_export_stats(callback: CallbackQuery, db: Database, config: Config) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    data = await db.stats()
    premium_until_list = await db.get_all_premium_until()
    premium_active = sum(1 for value in premium_until_list if is_premium_until(value))

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["metric", "value"])
    writer.writerow(["users", data["users"]])
    writer.writerow(["active_chats", data["active_chats"]])
    writer.writerow(["queue", data["queue"]])
    writer.writerow(["reports", data["reports"]])
    writer.writerow(["banned", data["banned"]])
    writer.writerow(["premium_active", premium_active])

    content = buffer.getvalue().encode("utf-8")
    file = BufferedInputFile(content, filename="stats.csv")
    await callback.message.answer_document(file)
    await callback.answer()


@router.callback_query(F.data == "admin:reports")
async def admin_reports(callback: CallbackQuery, db: Database, config: Config) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    report = await db.get_next_report()
    if not report:
        await callback.message.edit_text(
            tr(
                lang,
                "🧾 Жалобы\n----------------\nНовых жалоб нет.",
                "🧾 Reports\n----------------\nNo new reports.",
            ),
            reply_markup=admin_menu_keyboard(lang),
        )
        await callback.answer()
        return

    text = (
        tr(lang, "🧾 Жалоба\n", "🧾 Report\n")
        + "----------------\n"
        f"ID: {report['id']}\n"
        f"{tr(lang, 'От', 'From')}: {report['reporter_id']}\n"
        f"{tr(lang, 'На', 'Against')}: {report['reported_id']}\n"
        f"{tr(lang, 'Причина', 'Reason')}: {report_reason_label(report['reason'], lang)}\n"
        f"{tr(lang, 'Дата', 'Date')}: {report['created_at']}"
    )
    await callback.message.edit_text(
        text, reply_markup=report_action_keyboard(int(report["id"]), lang)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:report_ban:"))
async def admin_report_ban(callback: CallbackQuery, db: Database, config: Config) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    try:
        report_id = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer(tr(lang, "Неверный ID.", "Invalid ID."), show_alert=True)
        return

    report = await db.get_report_by_id(report_id)
    if not report:
        await callback.message.edit_text(
            tr(lang, "Жалоба не найдена.", "Report not found."),
            reply_markup=admin_menu_keyboard(lang),
        )
        await callback.answer()
        return

    target_id = int(report["reported_id"])
    await db.set_banned(target_id, True)
    await db.remove_from_queue(target_id)
    await db.set_state(target_id, STATE_IDLE)
    await end_chat(
        db,
        callback.bot,
        target_id,
        notify_user=False,
        collect_feedback=False,
        reason_ru="❌ Диалог завершен.",
        reason_en="❌ Chat ended.",
    )
    await safe_send_message(
        callback.bot,
        target_id,
        tr(
            await db.get_lang(target_id),
            "Ваш аккаунт заблокирован.",
            "Your account has been blocked.",
        ),
    )

    await db.resolve_report(report_id, "banned", callback.from_user.id)
    await db.add_incident(callback.from_user.id, target_id, "report_ban", str(report_id))

    await callback.message.edit_text(
        tr(
            lang,
            f"Готово. Пользователь {target_id} заблокирован.",
            f"Done. User {target_id} has been blocked.",
        ),
        reply_markup=admin_menu_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:report_ignore:"))
async def admin_report_ignore(callback: CallbackQuery, db: Database, config: Config) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    try:
        report_id = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer(tr(lang, "Неверный ID.", "Invalid ID."), show_alert=True)
        return

    report = await db.get_report_by_id(report_id)
    if not report:
        await callback.message.edit_text(
            tr(lang, "Жалоба не найдена.", "Report not found."),
            reply_markup=admin_menu_keyboard(lang),
        )
        await callback.answer()
        return

    await db.resolve_report(report_id, "ignored", callback.from_user.id)
    await db.add_incident(callback.from_user.id, int(report["reported_id"]), "report_ignore", str(report_id))

    await callback.message.edit_text(
        tr(
            lang,
            f"Жалоба {report_id} проигнорирована.",
            f"Report {report_id} ignored.",
        ),
        reply_markup=admin_menu_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:active_users")
async def admin_active_users(callback: CallbackQuery, db: Database, config: Config) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    user_ids = await db.get_active_user_ids()
    total = len(user_ids)

    if total == 0:
        await callback.message.edit_text(
            tr(
                lang,
                "👥 Активные пользователи: 0\n----------------\nНет активных сессий.",
                "👥 Active users: 0\n----------------\nNo active sessions.",
            ),
            reply_markup=admin_menu_keyboard(lang),
        )
        await callback.answer()
        return

    lines = []
    for idx, user_id in enumerate(user_ids, start=1):
        try:
            chat = await callback.bot.get_chat(user_id)
            name = _display_name(chat, lang)
            lines.append(f"{idx}. {name} — {user_id}")
        except Exception:
            lines.append(f"{idx}. {user_id} — {tr(lang, 'недоступен', 'unavailable')}")

    header = tr(lang, f"👥 Активные пользователи: {total}", f"👥 Active users: {total}")
    chunks = _chunk_lines(lines)

    # Update panel with summary and send the list in separate messages if needed.
    await callback.message.edit_text(
        tr(
            lang,
            f"{header}\n----------------\nСписок отправлен ниже.",
            f"{header}\n----------------\nThe list was sent below.",
        ),
        reply_markup=admin_menu_keyboard(lang),
    )

    for chunk in chunks:
        await callback.message.answer(f"{header}\n\n{chunk}")

    await callback.answer()


@router.callback_query(F.data == "admin:ban")
async def admin_ban_start(callback: CallbackQuery, db: Database, state: FSMContext, config: Config) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    await state.set_state(AdminStates.waiting_ban_id)
    await callback.message.answer(
        tr(lang, "Укажите user_id для бана:", "Enter user_id to ban:"),
        reply_markup=admin_cancel_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:unban")
async def admin_unban_start(callback: CallbackQuery, db: Database, state: FSMContext, config: Config) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    await state.set_state(AdminStates.waiting_unban_id)
    await callback.message.answer(
        tr(lang, "Укажите user_id для разбана:", "Enter user_id to unban:"),
        reply_markup=admin_cancel_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:cancel")
async def admin_cancel(callback: CallbackQuery, db: Database, state: FSMContext, config: Config) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    await state.clear()
    await callback.message.answer(
        tr(lang, "Отменено.", "Canceled."),
        reply_markup=admin_menu_keyboard(lang),
    )
    await callback.answer()


@router.message(AdminStates.waiting_ban_id)
async def admin_ban_input(message: Message, db: Database, state: FSMContext, config: Config) -> None:
    lang = await db.get_lang(message.from_user.id)
    if not _is_admin(message.from_user.id, config):
        await message.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."))
        return

    target_id = _parse_target_id(message.text or "")
    if not target_id:
        await message.answer(tr(lang, "Введите корректный user_id.", "Enter a valid user_id."))
        return

    await state.update_data(target_id=target_id)
    await state.set_state(AdminStates.confirm_ban)
    await message.answer(
        tr(
            lang,
            f"Подтвердить бан пользователя {target_id}?",
            f"Confirm ban for user {target_id}?",
        ),
        reply_markup=admin_confirm_keyboard("ban", lang),
    )


@router.callback_query(F.data == "admin:confirm_ban", AdminStates.confirm_ban)
async def admin_confirm_ban(
    callback: CallbackQuery, db: Database, state: FSMContext, config: Config
) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    data = await state.get_data()
    target_id = data.get("target_id")
    if not target_id:
        await state.clear()
        await callback.message.answer(
            tr(lang, "Не удалось получить user_id.", "Failed to get user_id."),
            reply_markup=admin_menu_keyboard(lang),
        )
        await callback.answer()
        return

    await db.set_banned(int(target_id), True)
    await db.remove_from_queue(int(target_id))
    await db.set_state(int(target_id), STATE_IDLE)

    await end_chat(
        db,
        callback.bot,
        int(target_id),
        notify_user=False,
        collect_feedback=False,
        reason_ru="❌ Диалог завершен.",
        reason_en="❌ Chat ended.",
    )
    await safe_send_message(
        callback.bot,
        int(target_id),
        tr(await db.get_lang(int(target_id)), "Ваш аккаунт заблокирован.", "Your account has been blocked."),
    )

    await state.clear()
    await callback.message.edit_text(
        tr(
            lang,
            f"Готово. Пользователь {target_id} заблокирован.",
            f"Done. User {target_id} has been blocked.",
        ),
        reply_markup=admin_menu_keyboard(lang),
    )
    await callback.answer()


@router.message(AdminStates.waiting_unban_id)
async def admin_unban_input(
    message: Message, db: Database, state: FSMContext, config: Config
) -> None:
    lang = await db.get_lang(message.from_user.id)
    if not _is_admin(message.from_user.id, config):
        await message.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."))
        return

    target_id = _parse_target_id(message.text or "")
    if not target_id:
        await message.answer(tr(lang, "Введите корректный user_id.", "Enter a valid user_id."))
        return

    await state.update_data(target_id=target_id)
    await state.set_state(AdminStates.confirm_unban)
    await message.answer(
        tr(
            lang,
            f"Подтвердить разбан пользователя {target_id}?",
            f"Confirm unban for user {target_id}?",
        ),
        reply_markup=admin_confirm_keyboard("unban", lang),
    )


@router.callback_query(F.data == "admin:confirm_unban", AdminStates.confirm_unban)
async def admin_confirm_unban(
    callback: CallbackQuery, db: Database, state: FSMContext, config: Config
) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    data = await state.get_data()
    target_id = data.get("target_id")
    if not target_id:
        await state.clear()
        await callback.message.answer(
            tr(lang, "Не удалось получить user_id.", "Failed to get user_id."),
            reply_markup=admin_menu_keyboard(lang),
        )
        await callback.answer()
        return

    await db.set_banned(int(target_id), False)
    await db.set_banned_until(int(target_id), "")
    await db.set_state(int(target_id), STATE_IDLE)

    await state.clear()
    await callback.message.edit_text(
        tr(
            lang,
            f"Готово. Пользователь {target_id} разблокирован.",
            f"Done. User {target_id} has been unblocked.",
        ),
        reply_markup=admin_menu_keyboard(lang),
    )
    await callback.answer()


@router.message(Command("ban"))
async def ban_user(message: Message, db: Database, config: Config) -> None:
    lang = await db.get_lang(message.from_user.id)
    if not _is_admin(message.from_user.id, config):
        await message.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."))
        return

    target_id = _parse_target_id(message.text or "")
    if not target_id:
        await message.answer(tr(lang, "Использование: /ban <user_id>", "Usage: /ban <user_id>"))
        return

    await db.set_banned(target_id, True)
    await db.remove_from_queue(target_id)
    await db.set_state(target_id, STATE_IDLE)

    # End active chat if any.
    await end_chat(
        db,
        message.bot,
        target_id,
        notify_user=False,
        collect_feedback=False,
        reason_ru="❌ Диалог завершен.",
        reason_en="❌ Chat ended.",
    )
    await safe_send_message(
        message.bot,
        target_id,
        tr(await db.get_lang(target_id), "Ваш аккаунт заблокирован.", "Your account has been blocked."),
    )

    await message.answer(
        tr(
            lang,
            f"Пользователь {target_id} заблокирован.",
            f"User {target_id} has been blocked.",
        )
    )
    await db.add_incident(message.from_user.id, target_id, "ban", "")


@router.message(Command("unban"))
async def unban_user(message: Message, db: Database, config: Config) -> None:
    lang = await db.get_lang(message.from_user.id)
    if not _is_admin(message.from_user.id, config):
        await message.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."))
        return

    target_id = _parse_target_id(message.text or "")
    if not target_id:
        await message.answer(tr(lang, "Использование: /unban <user_id>", "Usage: /unban <user_id>"))
        return

    await db.set_banned(target_id, False)
    await db.set_banned_until(target_id, "")
    await db.set_state(target_id, STATE_IDLE)
    await message.answer(
        tr(
            lang,
            f"Пользователь {target_id} разблокирован.",
            f"User {target_id} has been unblocked.",
        )
    )
    await db.add_incident(message.from_user.id, target_id, "unban", "")


@router.message(Command("tempban"))
async def tempban_user(message: Message, db: Database, config: Config) -> None:
    lang = await db.get_lang(message.from_user.id)
    if not _is_admin(message.from_user.id, config):
        await message.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."))
        return

    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer(
            tr(lang, "Использование: /tempban <user_id> <hours>", "Usage: /tempban <user_id> <hours>")
        )
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer(tr(lang, "Неверный user_id.", "Invalid user_id."))
        return

    hours = _parse_positive_hours(parts[2])
    if not hours:
        await message.answer(tr(lang, "hours должно быть целым числом > 0.", "hours must be an integer > 0."))
        return

    banned_until = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
    await db.set_banned_until(target_id, banned_until)
    await db.remove_from_queue(target_id)
    await db.set_state(target_id, STATE_IDLE)
    await end_chat(
        db,
        message.bot,
        target_id,
        notify_user=False,
        collect_feedback=False,
        reason_ru="❌ Диалог завершен.",
        reason_en="❌ Chat ended.",
    )
    await safe_send_message(
        message.bot,
        target_id,
        tr(
            await db.get_lang(target_id),
            f"Ваш аккаунт временно заблокирован до {format_until_text(banned_until)}.",
            f"Your account is temporarily blocked until {format_until_text(banned_until)}.",
        ),
    )
    await message.answer(
        tr(
            lang,
            f"Пользователь {target_id} заблокирован до {format_until_text(banned_until)}.",
            f"User {target_id} is blocked until {format_until_text(banned_until)}.",
        )
    )
    await db.add_incident(message.from_user.id, target_id, "tempban", f"{hours}h")


@router.message(Command("mute"))
async def mute_user(message: Message, db: Database, config: Config) -> None:
    lang = await db.get_lang(message.from_user.id)
    if not _is_admin(message.from_user.id, config):
        await message.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."))
        return

    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer(tr(lang, "Использование: /mute <user_id> <hours>", "Usage: /mute <user_id> <hours>"))
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer(tr(lang, "Неверный user_id.", "Invalid user_id."))
        return

    hours = _parse_positive_hours(parts[2])
    if not hours:
        await message.answer(tr(lang, "hours должно быть целым числом > 0.", "hours must be an integer > 0."))
        return

    muted_until = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
    await db.set_muted_until(target_id, muted_until)
    await safe_send_message(
        message.bot,
        target_id,
        tr(
            await db.get_lang(target_id),
            f"Вам выдан мут до {format_until_text(muted_until)}.",
            f"You are muted until {format_until_text(muted_until)}.",
        ),
    )
    await message.answer(
        tr(
            lang,
            f"Пользователю {target_id} выдан мут до {format_until_text(muted_until)}.",
            f"User {target_id} is muted until {format_until_text(muted_until)}.",
        )
    )
    await db.add_incident(message.from_user.id, target_id, "mute", f"{hours}h")


@router.message(Command("unmute"))
async def unmute_user(message: Message, db: Database, config: Config) -> None:
    lang = await db.get_lang(message.from_user.id)
    if not _is_admin(message.from_user.id, config):
        await message.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."))
        return

    target_id = _parse_target_id(message.text or "")
    if not target_id:
        await message.answer(tr(lang, "Использование: /unmute <user_id>", "Usage: /unmute <user_id>"))
        return

    await db.set_muted_until(target_id, "")
    await message.answer(
        tr(
            lang,
            f"Мут для {target_id} снят.",
            f"Mute removed for {target_id}.",
        )
    )
    await db.add_incident(message.from_user.id, target_id, "unmute", "")


@router.message(Command("stats"))
async def stats(message: Message, db: Database, config: Config) -> None:
    lang = await db.get_lang(message.from_user.id)
    if not _is_admin(message.from_user.id, config):
        await message.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."))
        return

    data = await db.stats()
    premium_until_list = await db.get_all_premium_until()
    premium_active = sum(1 for value in premium_until_list if is_premium_until(value))
    text = (
        tr(lang, "📊 Статистика\n", "📊 Statistics\n")
        + f"{tr(lang, 'Пользователи', 'Users')}: {data['users']}\n"
        + f"{tr(lang, 'Активные чаты', 'Active chats')}: {data['active_chats']}\n"
        + f"{tr(lang, 'В очереди', 'In queue')}: {data['queue']}\n"
        + f"{tr(lang, 'Жалобы', 'Reports')}: {data['reports']}\n"
        + f"{tr(lang, 'Заблокированные', 'Blocked')}: {data['banned']}\n"
        + f"{tr(lang, 'Premium активные', 'Premium active')}: {premium_active}"
    )
    await message.answer(text)


@router.message(Command("export_stats"))
async def export_stats(message: Message, db: Database, config: Config) -> None:
    lang = await db.get_lang(message.from_user.id)
    if not _is_admin(message.from_user.id, config):
        await message.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."))
        return

    data = await db.stats()
    premium_until_list = await db.get_all_premium_until()
    premium_active = sum(1 for value in premium_until_list if is_premium_until(value))

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["metric", "value"])
    writer.writerow(["users", data["users"]])
    writer.writerow(["active_chats", data["active_chats"]])
    writer.writerow(["queue", data["queue"]])
    writer.writerow(["reports", data["reports"]])
    writer.writerow(["banned", data["banned"]])
    writer.writerow(["premium_active", premium_active])

    content = buffer.getvalue().encode("utf-8")
    file = BufferedInputFile(content, filename="stats.csv")
    await message.answer_document(file)
