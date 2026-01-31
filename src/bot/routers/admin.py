from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from ...config import Config
from ...db.database import Database
from ..keyboards.admin_menu import admin_cancel_keyboard, admin_menu_keyboard
from ..utils.chat import end_chat, safe_send_message
from ..utils.constants import STATE_IDLE

router = Router()

class AdminStates(StatesGroup):
    waiting_ban_id = State()
    waiting_unban_id = State()


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
        "📊 Статистика\n"
        f"Користувачі: {data['users']}\n"
        f"Активні чати: {data['active_chats']}\n"
        f"В черзі: {data['queue']}\n"
        f"Скарги: {data['reports']}"
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


@router.callback_query(F.data == "admin:active_users")
async def admin_active_users(callback: CallbackQuery, db: Database, config: Config) -> None:
    if not _is_admin(callback.from_user.id, config):
        await callback.answer("Недостатньо прав.", show_alert=True)
        return

    user_ids = await db.get_active_user_ids()
    total = len(user_ids)

    if total == 0:
        await callback.message.edit_text(
            "👥 Активні користувачі: 0",
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
        f"{header}\n\nСписок надіслано окремо.",
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

    await db.set_banned(target_id, True)
    await db.remove_from_queue(target_id)
    await db.set_state(target_id, STATE_IDLE)

    await end_chat(
        db,
        message.bot,
        target_id,
        notify_user=False,
        reason_text="❌ Діалог завершено.",
    )
    await safe_send_message(message.bot, target_id, "Ваш акаунт заблоковано.")

    await state.clear()
    await message.answer(f"Користувача {target_id} заблоковано.", reply_markup=admin_menu_keyboard())


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

    await db.set_banned(target_id, False)
    await db.set_state(target_id, STATE_IDLE)
    await state.clear()
    await message.answer(f"Користувача {target_id} розблоковано.", reply_markup=admin_menu_keyboard())


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


@router.message(Command("stats"))
async def stats(message: Message, db: Database, config: Config) -> None:
    if not _is_admin(message.from_user.id, config):
        await message.answer("Недостатньо прав.")
        return

    data = await db.stats()
    text = (
        "📊 Статистика\n"
        f"Користувачі: {data['users']}\n"
        f"Активні чати: {data['active_chats']}\n"
        f"В черзі: {data['queue']}\n"
        f"Скарги: {data['reports']}"
    )
    await message.answer(text)
