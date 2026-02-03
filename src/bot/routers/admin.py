import csv
import io

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
from ..utils.chat import end_chat, safe_send_message
from ..utils.constants import PREMIUM_INFO_TEXT, STATE_IDLE
from ..utils.premium import add_premium_days, is_premium_until

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


def _stats_text(data: dict[str, int]) -> str:
    return (
        "🧰 Адмін-панель\n"
        "----------------\n"
        "📊 Статистика\n"
        f"- Користувачі: {data['users']}\n"
        f"- Активні чати: {data['active_chats']}\n"
        f"- В черзі: {data['queue']}\n"
        f"- Скарги: {data['reports']}\n"
        f"- Заблоковані: {data['banned']}\n"
        "\n"
        "Дії доступні кнопками нижче."
    )


def _display_name(chat) -> str:
    if getattr(chat, "username", None):
        return f"@{chat.username}"
    name_parts = [chat.first_name or "", chat.last_name or ""]
    name = " ".join([p for p in name_parts if p]).strip()
    return name if name else "Без імені"


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
    if not _is_admin(message.from_user.id, config):
        await message.answer("Недостатньо прав.")
        return

    data = await db.stats()
    await message.answer(_stats_text(data), reply_markup=admin_menu_keyboard())


@router.message(Command("premium"))
async def premium_command(message: Message, db: Database, config: Config) -> None:
    parts = (message.text or "").split()
    if len(parts) == 1:
        await message.answer(PREMIUM_INFO_TEXT)
        return

    if not _is_admin(message.from_user.id, config):
        await message.answer("Недостатньо прав.")
        return

    if len(parts) < 3:
        await message.answer("Використання: /premium <user_id> <days>")
        return

    try:
        target_id = int(parts[1])
        days = int(parts[2])
    except ValueError:
        await message.answer("Невірний формат. Використання: /premium <user_id> <days>")
        return

    if days <= 0:
        await message.answer("Кількість днів має бути більшою за 0.")
        return

    current_until = await db.get_premium_until(target_id)
    new_until = add_premium_days(current_until, days)
    await db.set_premium_until(target_id, new_until)
    await message.answer(
        f"Premium активовано для {target_id} до {new_until}."
    )
    await db.add_incident(message.from_user.id, target_id, "premium_grant", f"{days}d")


@router.message(Command("premium_clear"))
async def premium_clear(message: Message, db: Database, config: Config) -> None:
    if not _is_admin(message.from_user.id, config):
        await message.answer("Недостатньо прав.")
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Використання: /premium_clear <user_id>")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("Невірний формат user_id.")
        return

    await db.set_premium_until(target_id, "")
    await message.answer(f"Premium для {target_id} вимкнено.")
    await db.add_incident(message.from_user.id, target_id, "premium_clear", "")


@router.message(F.text == "🧰 Адмін-панель")
async def admin_panel_button(message: Message, db: Database, config: Config) -> None:
    await admin_panel(message, db, config)


@router.callback_query(F.data == "admin:close")
async def admin_close(callback: CallbackQuery, config: Config) -> None:
    if not _is_admin(callback.from_user.id, config):
        await callback.answer("Недостатньо прав.", show_alert=True)
        return

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()


@router.callback_query(F.data.in_({"admin:stats", "admin:refresh"}))
async def admin_stats(callback: CallbackQuery, db: Database, config: Config) -> None:
    if not _is_admin(callback.from_user.id, config):
        await callback.answer("Недостатньо прав.", show_alert=True)
        return

    data = await db.stats()
    await callback.message.edit_text(_stats_text(data), reply_markup=admin_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:export_stats")
async def admin_export_stats(callback: CallbackQuery, db: Database, config: Config) -> None:
    if not _is_admin(callback.from_user.id, config):
        await callback.answer("Недостатньо прав.", show_alert=True)
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
    if not _is_admin(callback.from_user.id, config):
        await callback.answer("Недостатньо прав.", show_alert=True)
        return

    report = await db.get_next_report()
    if not report:
        await callback.message.edit_text(
            "🧾 Скарги\n----------------\nНових скарг немає.",
            reply_markup=admin_menu_keyboard(),
        )
        await callback.answer()
        return

    text = (
        "🧾 Скарга\n"
        "----------------\n"
        f"ID: {report['id']}\n"
        f"Від: {report['reporter_id']}\n"
        f"На: {report['reported_id']}\n"
        f"Причина: {report['reason']}\n"
        f"Дата: {report['created_at']}"
    )
    await callback.message.edit_text(
        text, reply_markup=report_action_keyboard(int(report["id"]))
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:report_ban:"))
async def admin_report_ban(callback: CallbackQuery, db: Database, config: Config) -> None:
    if not _is_admin(callback.from_user.id, config):
        await callback.answer("Недостатньо прав.", show_alert=True)
        return

    try:
        report_id = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Невірний ID.", show_alert=True)
        return

    report = await db.get_report_by_id(report_id)
    if not report:
        await callback.message.edit_text("Скаргу не знайдено.", reply_markup=admin_menu_keyboard())
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
        reason_text="❌ Діалог завершено.",
    )
    await safe_send_message(callback.bot, target_id, "Ваш акаунт заблоковано.")

    await db.resolve_report(report_id, "banned", callback.from_user.id)
    await db.add_incident(callback.from_user.id, target_id, "report_ban", str(report_id))

    await callback.message.edit_text(
        f"Готово. Користувача {target_id} заблоковано.",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:report_ignore:"))
async def admin_report_ignore(callback: CallbackQuery, db: Database, config: Config) -> None:
    if not _is_admin(callback.from_user.id, config):
        await callback.answer("Недостатньо прав.", show_alert=True)
        return

    try:
        report_id = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer("Невірний ID.", show_alert=True)
        return

    report = await db.get_report_by_id(report_id)
    if not report:
        await callback.message.edit_text("Скаргу не знайдено.", reply_markup=admin_menu_keyboard())
        await callback.answer()
        return

    await db.resolve_report(report_id, "ignored", callback.from_user.id)
    await db.add_incident(callback.from_user.id, int(report["reported_id"]), "report_ignore", str(report_id))

    await callback.message.edit_text(
        f"Скаргу {report_id} проігноровано.",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:active_users")
async def admin_active_users(callback: CallbackQuery, db: Database, config: Config) -> None:
    if not _is_admin(callback.from_user.id, config):
        await callback.answer("Недостатньо прав.", show_alert=True)
        return

    user_ids = await db.get_active_user_ids()
    total = len(user_ids)

    if total == 0:
        await callback.message.edit_text(
            "👥 Активні користувачі: 0\n----------------\nНемає активних сесій.",
            reply_markup=admin_menu_keyboard(),
        )
        await callback.answer()
        return

    lines = []
    for idx, user_id in enumerate(user_ids, start=1):
        try:
            chat = await callback.bot.get_chat(user_id)
            name = _display_name(chat)
            lines.append(f"{idx}. {name} — {user_id}")
        except Exception:
            lines.append(f"{idx}. {user_id} — недоступний")

    header = f"👥 Активні користувачі: {total}"
    chunks = _chunk_lines(lines)

    # Update panel with summary and send the list in separate messages if needed.
    await callback.message.edit_text(
        f"{header}\n----------------\nСписок надіслано нижче.",
        reply_markup=admin_menu_keyboard(),
    )

    for chunk in chunks:
        await callback.message.answer(f"{header}\n\n{chunk}")

    await callback.answer()


@router.callback_query(F.data == "admin:ban")
async def admin_ban_start(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not _is_admin(callback.from_user.id, config):
        await callback.answer("Недостатньо прав.", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_ban_id)
    await callback.message.answer("Вкажіть user_id для бану:", reply_markup=admin_cancel_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:unban")
async def admin_unban_start(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not _is_admin(callback.from_user.id, config):
        await callback.answer("Недостатньо прав.", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_unban_id)
    await callback.message.answer("Вкажіть user_id для розбану:", reply_markup=admin_cancel_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:cancel")
async def admin_cancel(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    if not _is_admin(callback.from_user.id, config):
        await callback.answer("Недостатньо прав.", show_alert=True)
        return

    await state.clear()
    await callback.message.answer("Скасовано.", reply_markup=admin_menu_keyboard())
    await callback.answer()


@router.message(AdminStates.waiting_ban_id)
async def admin_ban_input(message: Message, db: Database, state: FSMContext, config: Config) -> None:
    if not _is_admin(message.from_user.id, config):
        await message.answer("Недостатньо прав.")
        return

    target_id = _parse_target_id(message.text or "")
    if not target_id:
        await message.answer("Введіть коректний user_id.")
        return

    await state.update_data(target_id=target_id)
    await state.set_state(AdminStates.confirm_ban)
    await message.answer(
        f"Підтвердити бан користувача {target_id}?",
        reply_markup=admin_confirm_keyboard("ban"),
    )


@router.callback_query(F.data == "admin:confirm_ban", AdminStates.confirm_ban)
async def admin_confirm_ban(
    callback: CallbackQuery, db: Database, state: FSMContext, config: Config
) -> None:
    if not _is_admin(callback.from_user.id, config):
        await callback.answer("Недостатньо прав.", show_alert=True)
        return

    data = await state.get_data()
    target_id = data.get("target_id")
    if not target_id:
        await state.clear()
        await callback.message.answer("Не вдалося отримати user_id.", reply_markup=admin_menu_keyboard())
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
        reason_text="❌ Діалог завершено.",
    )
    await safe_send_message(callback.bot, int(target_id), "Ваш акаунт заблоковано.")

    await state.clear()
    await callback.message.edit_text(
        f"Готово. Користувача {target_id} заблоковано.",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()


@router.message(AdminStates.waiting_unban_id)
async def admin_unban_input(
    message: Message, db: Database, state: FSMContext, config: Config
) -> None:
    if not _is_admin(message.from_user.id, config):
        await message.answer("Недостатньо прав.")
        return

    target_id = _parse_target_id(message.text or "")
    if not target_id:
        await message.answer("Введіть коректний user_id.")
        return

    await state.update_data(target_id=target_id)
    await state.set_state(AdminStates.confirm_unban)
    await message.answer(
        f"Підтвердити розбан користувача {target_id}?",
        reply_markup=admin_confirm_keyboard("unban"),
    )


@router.callback_query(F.data == "admin:confirm_unban", AdminStates.confirm_unban)
async def admin_confirm_unban(
    callback: CallbackQuery, db: Database, state: FSMContext, config: Config
) -> None:
    if not _is_admin(callback.from_user.id, config):
        await callback.answer("Недостатньо прав.", show_alert=True)
        return

    data = await state.get_data()
    target_id = data.get("target_id")
    if not target_id:
        await state.clear()
        await callback.message.answer("Не вдалося отримати user_id.", reply_markup=admin_menu_keyboard())
        await callback.answer()
        return

    await db.set_banned(int(target_id), False)
    await db.set_state(int(target_id), STATE_IDLE)

    await state.clear()
    await callback.message.edit_text(
        f"Готово. Користувача {target_id} розблоковано.",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()


@router.message(Command("ban"))
async def ban_user(message: Message, db: Database, config: Config) -> None:
    if not _is_admin(message.from_user.id, config):
        await message.answer("Недостатньо прав.")
        return

    target_id = _parse_target_id(message.text or "")
    if not target_id:
        await message.answer("Використання: /ban <user_id>")
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
        reason_text="❌ Діалог завершено.",
    )
    await safe_send_message(message.bot, target_id, "Ваш акаунт заблоковано.")

    await message.answer(f"Користувача {target_id} заблоковано.")
    await db.add_incident(message.from_user.id, target_id, "ban", "")


@router.message(Command("unban"))
async def unban_user(message: Message, db: Database, config: Config) -> None:
    if not _is_admin(message.from_user.id, config):
        await message.answer("Недостатньо прав.")
        return

    target_id = _parse_target_id(message.text or "")
    if not target_id:
        await message.answer("Використання: /unban <user_id>")
        return

    await db.set_banned(target_id, False)
    await db.set_state(target_id, STATE_IDLE)
    await message.answer(f"Користувача {target_id} розблоковано.")
    await db.add_incident(message.from_user.id, target_id, "unban", "")


@router.message(Command("stats"))
async def stats(message: Message, db: Database, config: Config) -> None:
    if not _is_admin(message.from_user.id, config):
        await message.answer("Недостатньо прав.")
        return

    data = await db.stats()
    premium_until_list = await db.get_all_premium_until()
    premium_active = sum(1 for value in premium_until_list if is_premium_until(value))
    text = (
        "📊 Статистика\n"
        f"Користувачі: {data['users']}\n"
        f"Активні чати: {data['active_chats']}\n"
        f"В черзі: {data['queue']}\n"
        f"Скарги: {data['reports']}\n"
        f"Заблоковані: {data['banned']}\n"
        f"Premium активні: {premium_active}"
    )
    await message.answer(text)


@router.message(Command("export_stats"))
async def export_stats(message: Message, db: Database, config: Config) -> None:
    if not _is_admin(message.from_user.id, config):
        await message.answer("Недостатньо прав.")
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
