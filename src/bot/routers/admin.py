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
    admin_media_item_keyboard,
    admin_media_keyboard,
    admin_menu_keyboard,
    report_action_keyboard,
)
from ..keyboards.report_menu import report_reason_label
from ..utils.chat import (
    end_chat,
    safe_edit_message_reply_markup,
    safe_edit_message_text,
    safe_send_message,
)
from ..utils.constants import PREMIUM_INFO_TEXT_EN, PREMIUM_INFO_TEXT_RU, STATE_IDLE
from ..utils.i18n import button_variants, tr
from ..utils.premium import add_premium_days, is_premium_until
from ..utils.users import format_until_text

router = Router()

MEDIA_RETENTION_DAYS = 3
MEDIA_PAGE_SIZE = 5

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


def _identity_text(chat, lang: str) -> str:
    username = f"@{chat.username}" if getattr(chat, "username", None) else "—"
    name_parts = [chat.first_name or "", chat.last_name or ""]
    full_name = " ".join([p for p in name_parts if p]).strip() or tr(lang, "Без имени", "No name")
    return (
        f"{tr(lang, 'Ник', 'Username')}: {username} | "
        f"{tr(lang, 'Имя', 'Name')}: {full_name}"
    )


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


def _short_text(value: str, max_len: int = 120) -> str:
    normalized = " ".join((value or "").split())
    if len(normalized) <= max_len:
        return normalized
    return normalized[: max_len - 1] + "…"


def _media_type_label(media_type: str, lang: str) -> str:
    labels = {
        "photo": tr(lang, "Фото", "Photo"),
        "video": tr(lang, "Видео", "Video"),
        "voice": tr(lang, "Голосовое", "Voice"),
        "video_note": tr(lang, "Кружок", "Video note"),
        "sticker": tr(lang, "Стикер", "Sticker"),
        "document": tr(lang, "Документ", "Document"),
        "audio": tr(lang, "Аудио", "Audio"),
        "animation": tr(lang, "GIF/анимация", "GIF/animation"),
    }
    return labels.get(media_type, media_type)


def _media_panel_text(
    rows: list,
    page: int,
    total: int,
    lang: str,
) -> str:
    total_pages = max((total + MEDIA_PAGE_SIZE - 1) // MEDIA_PAGE_SIZE, 1)
    lines = [
        tr(lang, "🖼 Медиа файлы", "🖼 Media Files"),
        "----------------",
        tr(
            lang,
            f"Храним медиа из переписок за последние {MEDIA_RETENTION_DAYS} дня.",
            f"Chat media from the last {MEDIA_RETENTION_DAYS} days is stored here.",
        ),
        tr(
            lang,
            f"Записей: {total} | Страница {page + 1}/{total_pages}",
            f"Records: {total} | Page {page + 1}/{total_pages}",
        ),
        "",
    ]

    if not rows:
        lines.append(tr(lang, "Нет медиа за выбранный период.", "No media for the selected period."))
        return "\n".join(lines)

    for idx, row in enumerate(rows, start=1 + page * MEDIA_PAGE_SIZE):
        caption = _short_text(row["caption"] or "—")
        lines.append(
            f"{idx}. {_media_type_label(row['media_type'], lang)} | "
            f"{tr(lang, 'от', 'from')} {row['sender_id']} -> {row['receiver_id']} | "
            f"{row['created_at']}"
        )
        lines.append(f"   {tr(lang, 'Подпись', 'Caption')}: {caption}")

    lines.append("")
    lines.append(
        tr(
            lang,
            "Сами медиа отправлены ниже отдельными сообщениями.",
            "The media files themselves are sent below as separate messages.",
        )
    )
    return "\n".join(lines)


def _media_preview_caption(row, lang: str) -> str:
    lines = [
        f"🖼 {_media_type_label(row['media_type'], lang)}",
        f"ID: {row['id']}",
        f"{tr(lang, 'От', 'From')}: {row['sender_id']}",
        f"{tr(lang, 'Кому', 'To')}: {row['receiver_id']}",
        f"{tr(lang, 'Дата', 'Date')}: {row['created_at']}",
    ]
    if row["caption"]:
        lines.append(f"{tr(lang, 'Подпись', 'Caption')}: {_short_text(row['caption'], 500)}")
    caption = "\n".join(lines)
    return caption[:900]


async def _send_media_preview(callback: CallbackQuery, row, lang: str) -> None:
    caption = _media_preview_caption(row, lang)
    reply_markup = admin_media_item_keyboard(int(row["id"]), lang)
    try:
        if row["media_type"] == "video":
            await callback.bot.send_video(
                callback.from_user.id,
                row["file_id"],
                caption=caption,
                reply_markup=reply_markup,
            )
        elif row["media_type"] == "voice":
            await callback.bot.send_voice(
                callback.from_user.id,
                row["file_id"],
                caption=caption,
                reply_markup=reply_markup,
            )
        elif row["media_type"] == "video_note":
            await callback.bot.send_message(callback.from_user.id, caption)
            await callback.bot.send_video_note(
                callback.from_user.id,
                row["file_id"],
                reply_markup=reply_markup,
            )
        elif row["media_type"] == "sticker":
            await callback.bot.send_message(callback.from_user.id, caption)
            await callback.bot.send_sticker(
                callback.from_user.id,
                row["file_id"],
                reply_markup=reply_markup,
            )
        elif row["media_type"] == "document":
            await callback.bot.send_document(
                callback.from_user.id,
                row["file_id"],
                caption=caption,
                reply_markup=reply_markup,
            )
        elif row["media_type"] == "audio":
            await callback.bot.send_audio(
                callback.from_user.id,
                row["file_id"],
                caption=caption,
                reply_markup=reply_markup,
            )
        elif row["media_type"] == "animation":
            await callback.bot.send_animation(
                callback.from_user.id,
                row["file_id"],
                caption=caption,
                reply_markup=reply_markup,
            )
        else:
            await callback.bot.send_photo(
                callback.from_user.id,
                row["file_id"],
                caption=caption,
                reply_markup=reply_markup,
            )
    except Exception:
        await callback.message.answer(
            tr(
                lang,
                f"Не удалось открыть медиа ID {row['id']}. Возможно, файл больше недоступен в Telegram.",
                f"Failed to open media ID {row['id']}. The file may no longer be available in Telegram.",
            )
        )


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

    await safe_edit_message_reply_markup(callback.message, reply_markup=None)
    await callback.answer()


@router.callback_query(F.data.in_({"admin:stats", "admin:refresh"}))
async def admin_stats(callback: CallbackQuery, db: Database, config: Config) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    data = await db.stats()
    await safe_edit_message_text(
        callback.message,
        _stats_text(data, lang),
        reply_markup=admin_menu_keyboard(lang),
    )
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


@router.callback_query(F.data == "admin:media")
@router.callback_query(F.data.startswith("admin:media:"))
async def admin_media_archive(callback: CallbackQuery, db: Database, config: Config) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    page = 0
    if callback.data and callback.data.count(":") >= 2:
        try:
            page = max(0, int(callback.data.split(":")[2]))
        except ValueError:
            page = 0

    total = await db.count_recent_media_records(MEDIA_RETENTION_DAYS)
    if total == 0:
        await safe_edit_message_text(
            callback.message,
            tr(
                lang,
                "🖼 Медиа файлы\n----------------\nЗа последние 3 дня медиа не найдены.",
                "🖼 Media Files\n----------------\nNo media was found for the last 3 days.",
            ),
            reply_markup=admin_menu_keyboard(lang),
        )
        await callback.answer()
        return

    max_page = max((total - 1) // MEDIA_PAGE_SIZE, 0)
    page = min(page, max_page)
    rows = await db.get_recent_media_records(
        retention_days=MEDIA_RETENTION_DAYS,
        limit=MEDIA_PAGE_SIZE,
        offset=page * MEDIA_PAGE_SIZE,
    )

    await safe_edit_message_text(
        callback.message,
        _media_panel_text(rows, page, total, lang),
        reply_markup=admin_media_keyboard(page, page > 0, page < max_page, lang),
    )

    for row in rows:
        await _send_media_preview(callback, row, lang)

    await callback.answer()


@router.callback_query(F.data.startswith("admin:media_delete:"))
async def admin_media_delete(callback: CallbackQuery, db: Database, config: Config) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    try:
        media_id = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer(tr(lang, "Неверный ID.", "Invalid ID."), show_alert=True)
        return

    row = await db.get_media_record_by_id(media_id)
    if not row:
        await callback.answer(
            tr(lang, "Запись уже удалена.", "The record has already been deleted."),
            show_alert=True,
        )
        return

    await db.delete_media_record(media_id)
    if callback.message:
        await safe_edit_message_reply_markup(callback.message, reply_markup=None)
    await callback.answer(tr(lang, "Медиа удалено из архива.", "Media removed from archive."), show_alert=True)


@router.callback_query(F.data == "admin:reports")
async def admin_reports(callback: CallbackQuery, db: Database, config: Config) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    report = await db.get_next_report()
    if not report:
        await safe_edit_message_text(callback.message,
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
    await safe_edit_message_text(callback.message,
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
        await safe_edit_message_text(callback.message,
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

    await safe_edit_message_text(callback.message,
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
        await safe_edit_message_text(callback.message,
            tr(lang, "Жалоба не найдена.", "Report not found."),
            reply_markup=admin_menu_keyboard(lang),
        )
        await callback.answer()
        return

    await db.resolve_report(report_id, "ignored", callback.from_user.id)
    await db.add_incident(callback.from_user.id, int(report["reported_id"]), "report_ignore", str(report_id))

    await safe_edit_message_text(callback.message,
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
        await safe_edit_message_text(callback.message,
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
            lines.append(f"{idx}. {_identity_text(chat, lang)} | ID: {user_id}")
        except Exception:
            lines.append(f"{idx}. {user_id} — {tr(lang, 'недоступен', 'unavailable')}")

    header = tr(lang, f"👥 Активные пользователи: {total}", f"👥 Active users: {total}")
    chunks = _chunk_lines(lines)

    # Update panel with summary and send the list in separate messages if needed.
    await safe_edit_message_text(callback.message,
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
    await safe_edit_message_text(callback.message,
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
    await safe_edit_message_text(callback.message,
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
