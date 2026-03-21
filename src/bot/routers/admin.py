import csv
import io
import secrets
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from ...config import Config
from ...db.database import Database
from ..keyboards.admin_menu import (
    admin_cancel_keyboard,
    admin_confirm_keyboard,
    admin_media_item_keyboard,
    admin_media_keyboard,
    admin_menu_keyboard,
    admin_promos_keyboard,
    admin_user_card_keyboard,
    report_action_keyboard,
)
from ..keyboards.report_menu import report_reason_label
from ..utils.chat import (
    end_chat,
    safe_edit_message_reply_markup,
    safe_edit_message_text,
    safe_send_message,
)
from ..utils.constants import (
    PREMIUM_INFO_TEXT_EN,
    PREMIUM_INFO_TEXT_RU,
    STATE_IDLE,
)
from ..utils.i18n import button_variants, tr
from ..utils.premium import add_premium_days
from ..utils.users import format_until_text

router = Router()

MEDIA_RETENTION_DAYS = 3
MEDIA_PAGE_SIZE = 5
USER_SEARCH_LIMIT = 8
PROMO_LIST_LIMIT = 8

class AdminStates(StatesGroup):
    waiting_ban_id = State()
    confirm_ban = State()
    waiting_unban_id = State()
    confirm_unban = State()
    waiting_search_query = State()
    waiting_promo_days = State()
    waiting_promo_limit = State()


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


def _parse_positive_int(text: str) -> int | None:
    try:
        value = int(text.strip())
    except ValueError:
        return None
    return value if value > 0 else None


def _percent(part: int, total: int) -> str:
    if total <= 0:
        return "0%"
    return f"{(part / total) * 100:.1f}%"


def _stats_text(data: dict[str, int], lang: str) -> str:
    return (
        tr(lang, "🧰 Админ-панель\n", "🧰 Admin Panel\n")
        + "----------------\n"
        + tr(lang, "📊 Статистика\n", "📊 Statistics\n")
        + f"- {tr(lang, 'Пользователи', 'Users')}: {data['users']}\n"
        + f"- {tr(lang, 'Новые за 24ч', 'New in 24h')}: {data['new_users_24h']}\n"
        + f"- {tr(lang, 'Новые за 7д', 'New in 7d')}: {data['new_users_7d']}\n"
        + f"- {tr(lang, 'Активные за 24ч', 'Active in 24h')}: {data['active_users_24h']}\n"
        + f"- {tr(lang, 'Активные чаты', 'Active chats')}: {data['active_chats']}\n"
        + f"- {tr(lang, 'Бот-чаты активные', 'Active bot chats')}: {data['active_virtual_chats']}\n"
        + f"- {tr(lang, 'В очереди', 'In queue')}: {data['queue']}\n"
        + f"- {tr(lang, 'Жалобы', 'Reports')}: {data['reports']}\n"
        + f"- {tr(lang, 'Заблокированные', 'Blocked')}: {data['banned']}\n"
        + f"- {tr(lang, 'Premium активные', 'Premium active')}: {data['premium_active']}\n"
        + f"- {tr(lang, 'Premium покупатели', 'Premium buyers')}: {data['premium_buyers']}\n"
        + f"- {tr(lang, 'Покупки premium', 'Premium purchases')}: {data['premium_purchases']}\n"
        + f"- {tr(lang, 'Выручка Stars', 'Revenue Stars')}: {data['revenue_xtr']}\n"
        + f"- {tr(lang, 'Используют ботов', 'Use virtual bots')}: {data['virtual_users']}\n"
        + f"- {tr(lang, 'Промокоды', 'Promo codes')}: {data['promo_codes']}\n"
        + "\n"
        + tr(lang, "📈 Воронка\n", "📈 Funnel\n")
        + f"- {tr(lang, 'Зарегистрировались', 'Registered')}: {data['users']}\n"
        + f"- {tr(lang, 'Были активны 24ч', 'Active in 24h')}: {data['active_users_24h']} ({_percent(data['active_users_24h'], data['users'])})\n"
        + f"- {tr(lang, 'Дошли до чатов', 'Reached chats')}: {data['engaged_users']} ({_percent(data['engaged_users'], data['users'])})\n"
        + f"- {tr(lang, 'Купили premium', 'Bought premium')}: {data['premium_buyers']} ({_percent(data['premium_buyers'], data['users'])})\n"
        + f"- {tr(lang, 'Пользовались ботами', 'Used virtual bots')}: {data['virtual_users']} ({_percent(data['virtual_users'], data['users'])})\n"
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


def _stored_identity_text(row, lang: str) -> str:
    username = f"@{row['username']}" if row["username"] else "—"
    full_name = " ".join([part for part in [row["first_name"], row["last_name"]] if part]).strip()
    full_name = full_name or tr(lang, "Без имени", "No name")
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


def _status_label(row, lang: str) -> str:
    if bool(row["is_banned"]):
        return tr(lang, "забанен", "banned")
    if row["banned_until"]:
        return tr(lang, "временный бан", "temporary ban")
    if row["muted_until"]:
        return tr(lang, "мут", "muted")
    state = (row["state"] or "").strip()
    labels = {
        "idle": tr(lang, "свободен", "idle"),
        "searching": tr(lang, "ищет", "searching"),
        "chatting": tr(lang, "в чате", "chatting"),
    }
    return labels.get(state, state or tr(lang, "неизвестно", "unknown"))


def _search_results_keyboard(rows, lang: str) -> InlineKeyboardMarkup:
    keyboard = []
    for row in rows:
        username = f"@{row['username']}" if row["username"] else f"ID {row['user_id']}"
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"{username}",
                    callback_data=f"admin:user:{int(row['user_id'])}",
                )
            ]
        )
    keyboard.append(
        [InlineKeyboardButton(text=tr(lang, "↩️ В админ-панель", "↩️ Back to panel"), callback_data="admin:stats")]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def _promo_panel_text(rows, lang: str) -> str:
    lines = [
        tr(lang, "🎟 Промокоды", "🎟 Promo Codes"),
        "----------------",
        tr(
            lang,
            "Генерация промокодов теперь доступна прямо из админ-панели.",
            "Promo codes can now be generated directly from the admin panel.",
        ),
        "",
    ]
    if not rows:
        lines.append(tr(lang, "Промокодов пока нет.", "There are no promo codes yet."))
        return "\n".join(lines)

    for row in rows:
        if int(row["usage_limit"]) > 0 and int(row["used_count"]) >= int(row["usage_limit"]):
            status = tr(lang, "исчерпан", "exhausted")
        else:
            status = tr(lang, "активен", "active") if bool(row["is_active"]) else tr(lang, "выключен", "disabled")
        lines.append(
            f"{row['code']} | {row['days']}d | "
            f"{row['used_count']}/{row['usage_limit']} | {status}"
        )
    return "\n".join(lines)


def _user_card_text(
    row,
    incidents_count: int,
    virtual_chats: int,
    lang: str,
) -> str:
    username = f"@{row['username']}" if row["username"] else "—"
    full_name = " ".join([part for part in [row["first_name"], row["last_name"]] if part]).strip()
    full_name = full_name or tr(lang, "Без имени", "No name")
    premium_until = row["premium_until"] or "—"
    banned_until = row["banned_until"] or "—"
    muted_until = row["muted_until"] or "—"
    last_seen = row["last_seen_at"] or "—"
    return (
        tr(lang, "👤 Карточка пользователя\n", "👤 User Card\n")
        + "----------------\n"
        + f"ID: {row['user_id']}\n"
        + f"{tr(lang, 'Ник', 'Username')}: {username}\n"
        + f"{tr(lang, 'Имя', 'Name')}: {full_name}\n"
        + f"{tr(lang, 'Статус', 'Status')}: {_status_label(row, lang)}\n"
        + f"{tr(lang, 'Создан', 'Created')}: {row['created_at']}\n"
        + f"{tr(lang, 'Последняя активность', 'Last seen')}: {last_seen}\n"
        + f"{tr(lang, 'Рейтинг', 'Rating')}: {row['rating']}\n"
        + f"{tr(lang, 'Чатов', 'Chats')}: {row['chats_count']}\n"
        + f"{tr(lang, 'Чатов с ботами', 'Chats with bots')}: {virtual_chats}\n"
        + f"{tr(lang, 'Premium до', 'Premium until')}: {premium_until}\n"
        + f"{tr(lang, 'Бан до', 'Banned until')}: {banned_until}\n"
        + f"{tr(lang, 'Мут до', 'Muted until')}: {muted_until}\n"
        + f"{tr(lang, 'Инцидентов', 'Incidents')}: {incidents_count}"
    )


def _user_incidents_text(user_id: int, rows, lang: str) -> str:
    lines = [
        tr(lang, f"📜 История пользователя {user_id}", f"📜 User History {user_id}"),
        "----------------",
    ]
    if not rows:
        lines.append(tr(lang, "Инцидентов нет.", "No incidents found."))
        return "\n".join(lines)
    for row in rows:
        payload = _short_text(row["payload"] or "—", 80)
        lines.append(
            f"{row['created_at']} | {row['type']} | "
            f"A:{row['actor_id']} -> T:{row['target_id']} | {payload}"
        )
    return "\n".join(lines)


async def _render_user_card(message_obj, db: Database, user_id: int, lang: str) -> None:
    row = await db.get_user(user_id)
    if not row:
        await safe_edit_message_text(
            message_obj,
            tr(lang, "Пользователь не найден.", "User not found."),
            reply_markup=admin_menu_keyboard(lang),
        )
        return

    incidents_count = await db.count_incidents_for_user(user_id)
    virtual_chats = await db.count_virtual_chats_for_user(user_id)
    await safe_edit_message_text(
        message_obj,
        _user_card_text(row, incidents_count, virtual_chats, lang),
        reply_markup=admin_user_card_keyboard(user_id, bool(row["is_banned"]), lang),
    )


def _generate_promo_code() -> str:
    return f"GC{secrets.token_hex(3).upper()}"


async def _apply_ban_for_user(db: Database, bot, target_id: int) -> None:
    await db.set_banned(target_id, True)
    await db.remove_from_queue(target_id)
    await db.set_state(target_id, STATE_IDLE)
    await end_chat(
        db,
        bot,
        target_id,
        notify_user=False,
        collect_feedback=False,
        reason_ru="❌ Диалог завершен.",
        reason_en="❌ Chat ended.",
    )
    await safe_send_message(
        bot,
        target_id,
        tr(await db.get_lang(target_id), "Ваш аккаунт заблокирован.", "Your account has been blocked."),
    )


async def _apply_unban_for_user(db: Database, target_id: int) -> None:
    await db.set_banned(target_id, False)
    await db.set_banned_until(target_id, "")
    await db.set_state(target_id, STATE_IDLE)


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

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["metric", "value"])
    writer.writerow(["users", data["users"]])
    writer.writerow(["new_users_24h", data["new_users_24h"]])
    writer.writerow(["new_users_7d", data["new_users_7d"]])
    writer.writerow(["active_users_24h", data["active_users_24h"]])
    writer.writerow(["active_chats", data["active_chats"]])
    writer.writerow(["active_virtual_chats", data["active_virtual_chats"]])
    writer.writerow(["queue", data["queue"]])
    writer.writerow(["reports", data["reports"]])
    writer.writerow(["banned", data["banned"]])
    writer.writerow(["engaged_users", data["engaged_users"]])
    writer.writerow(["premium_active", data["premium_active"]])
    writer.writerow(["premium_buyers", data["premium_buyers"]])
    writer.writerow(["premium_purchases", data["premium_purchases"]])
    writer.writerow(["revenue_xtr", data["revenue_xtr"]])
    writer.writerow(["virtual_users", data["virtual_users"]])
    writer.writerow(["promo_users", data["promo_users"]])
    writer.writerow(["promo_codes", data["promo_codes"]])

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


@router.callback_query(F.data == "admin:search")
async def admin_search_start(callback: CallbackQuery, db: Database, state: FSMContext, config: Config) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    await state.set_state(AdminStates.waiting_search_query)
    await callback.message.answer(
        tr(
            lang,
            "Введите user_id или @username для поиска.",
            "Enter user_id or @username to search.",
        ),
        reply_markup=admin_cancel_keyboard(lang),
    )
    await callback.answer()


@router.message(AdminStates.waiting_search_query)
async def admin_search_input(
    message: Message, db: Database, state: FSMContext, config: Config
) -> None:
    lang = await db.get_lang(message.from_user.id)
    if not _is_admin(message.from_user.id, config):
        await message.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."))
        return

    query = (message.text or "").strip()
    if not query:
        await message.answer(
            tr(lang, "Введите user_id или @username.", "Enter user_id or @username.")
        )
        return

    results = await db.search_users(query, USER_SEARCH_LIMIT)
    await state.clear()

    if not results:
        await message.answer(
            tr(lang, "Ничего не найдено.", "Nothing found."),
            reply_markup=admin_menu_keyboard(lang),
        )
        return

    if len(results) == 1:
        row = results[0]
        incidents_count = await db.count_incidents_for_user(int(row["user_id"]))
        virtual_chats = await db.count_virtual_chats_for_user(int(row["user_id"]))
        await message.answer(
            _user_card_text(row, incidents_count, virtual_chats, lang),
            reply_markup=admin_user_card_keyboard(int(row["user_id"]), bool(row["is_banned"]), lang),
        )
        return

    lines = [tr(lang, "🔎 Результаты поиска", "🔎 Search Results"), "----------------"]
    for row in results:
        lines.append(f"{row['user_id']} | {_stored_identity_text(row, lang)}")
    await message.answer(
        "\n".join(lines),
        reply_markup=_search_results_keyboard(results, lang),
    )


@router.callback_query(F.data.startswith("admin:user:"))
async def admin_user_card(callback: CallbackQuery, db: Database, config: Config) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    try:
        user_id = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer(tr(lang, "Неверный user_id.", "Invalid user_id."), show_alert=True)
        return

    await _render_user_card(callback.message, db, user_id, lang)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:user_history:"))
async def admin_user_history(callback: CallbackQuery, db: Database, config: Config) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    try:
        user_id = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer(tr(lang, "Неверный user_id.", "Invalid user_id."), show_alert=True)
        return

    rows = await db.get_recent_incidents_for_user(user_id, limit=15)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr(lang, "↩️ К карточке", "↩️ Back to card"),
                    callback_data=f"admin:user:{user_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr(lang, "↩️ В админ-панель", "↩️ Back to panel"),
                    callback_data="admin:stats",
                )
            ],
        ]
    )
    await safe_edit_message_text(
        callback.message,
        _user_incidents_text(user_id, rows, lang),
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:user_ban:"))
async def admin_user_ban(callback: CallbackQuery, db: Database, config: Config) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    try:
        user_id = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer(tr(lang, "Неверный user_id.", "Invalid user_id."), show_alert=True)
        return

    await _apply_ban_for_user(db, callback.bot, user_id)
    await db.add_incident(callback.from_user.id, user_id, "ban", "user_card")
    await _render_user_card(callback.message, db, user_id, lang)
    await callback.answer(tr(lang, "Пользователь заблокирован.", "User blocked."), show_alert=True)


@router.callback_query(F.data.startswith("admin:user_unban:"))
async def admin_user_unban(callback: CallbackQuery, db: Database, config: Config) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    try:
        user_id = int((callback.data or "").split(":")[2])
    except (IndexError, ValueError):
        await callback.answer(tr(lang, "Неверный user_id.", "Invalid user_id."), show_alert=True)
        return

    await _apply_unban_for_user(db, user_id)
    await db.add_incident(callback.from_user.id, user_id, "unban", "user_card")
    await _render_user_card(callback.message, db, user_id, lang)
    await callback.answer(tr(lang, "Пользователь разблокирован.", "User unblocked."), show_alert=True)


@router.callback_query(F.data == "admin:promos")
async def admin_promos(callback: CallbackQuery, db: Database, config: Config) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    rows = await db.get_recent_promo_codes(PROMO_LIST_LIMIT)
    await safe_edit_message_text(
        callback.message,
        _promo_panel_text(rows, lang),
        reply_markup=admin_promos_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "admin:promo_create")
async def admin_promo_create_start(
    callback: CallbackQuery, db: Database, state: FSMContext, config: Config
) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    await state.set_state(AdminStates.waiting_promo_days)
    await callback.message.answer(
        tr(
            lang,
            "Введите количество дней для промокода.",
            "Enter the number of days for the promo code.",
        ),
        reply_markup=admin_cancel_keyboard(lang),
    )
    await callback.answer()


@router.message(AdminStates.waiting_promo_days)
async def admin_promo_days_input(
    message: Message, db: Database, state: FSMContext, config: Config
) -> None:
    lang = await db.get_lang(message.from_user.id)
    if not _is_admin(message.from_user.id, config):
        await message.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."))
        return

    days = _parse_positive_int(message.text or "")
    if not days:
        await message.answer(tr(lang, "Введите число дней > 0.", "Enter a number of days > 0."))
        return

    await state.update_data(promo_days=days)
    await state.set_state(AdminStates.waiting_promo_limit)
    await message.answer(
        tr(
            lang,
            "Введите лимит использований для промокода.",
            "Enter the usage limit for the promo code.",
        ),
        reply_markup=admin_cancel_keyboard(lang),
    )


@router.message(AdminStates.waiting_promo_limit)
async def admin_promo_limit_input(
    message: Message, db: Database, state: FSMContext, config: Config
) -> None:
    lang = await db.get_lang(message.from_user.id)
    if not _is_admin(message.from_user.id, config):
        await message.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."))
        return

    usage_limit = _parse_positive_int(message.text or "")
    if not usage_limit:
        await message.answer(tr(lang, "Введите лимит > 0.", "Enter a limit > 0."))
        return

    data = await state.get_data()
    days = int(data.get("promo_days") or 0)
    if days <= 0:
        await state.clear()
        await message.answer(
            tr(lang, "Не удалось получить количество дней.", "Failed to get the number of days."),
            reply_markup=admin_menu_keyboard(lang),
        )
        return

    promo_code = ""
    for _ in range(5):
        candidate = _generate_promo_code()
        if not await db.get_managed_promo_code(candidate):
            promo_code = candidate
            break
    if not promo_code:
        await state.clear()
        await message.answer(
            tr(lang, "Не удалось сгенерировать код. Попробуйте еще раз.", "Failed to generate a code. Try again."),
            reply_markup=admin_menu_keyboard(lang),
        )
        return

    await db.create_promo_code(promo_code, days, usage_limit, message.from_user.id)
    await db.add_incident(
        message.from_user.id,
        None,
        "promo_generated",
        f"{promo_code}|{days}|{usage_limit}",
    )
    await state.clear()
    await message.answer(
        tr(
            lang,
            f"🎟 Промокод создан\nКод: {promo_code}\nДней: {days}\nЛимит: {usage_limit}\n\nИспользование: /promo {promo_code}",
            f"🎟 Promo code created\nCode: {promo_code}\nDays: {days}\nLimit: {usage_limit}\n\nUsage: /promo {promo_code}",
        ),
        reply_markup=admin_promos_keyboard(lang),
    )


@router.callback_query(F.data == "admin:active_users")
async def admin_active_users(callback: CallbackQuery, db: Database, config: Config) -> None:
    lang = await db.get_lang(callback.from_user.id)
    if not _is_admin(callback.from_user.id, config):
        await callback.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."), show_alert=True)
        return

    rows = await db.get_all_users()
    total = len(rows)

    if total == 0:
        await safe_edit_message_text(callback.message,
            tr(
                lang,
                "👥 Все пользователи: 0\n----------------\nВ базе пока нет пользователей.",
                "👥 All users: 0\n----------------\nThere are no users in the database yet.",
            ),
            reply_markup=admin_menu_keyboard(lang),
        )
        await callback.answer()
        return

    lines = []
    for idx, row in enumerate(rows, start=1):
        lines.append(
            f"{idx}. {_stored_identity_text(row, lang)} | ID: {row['user_id']} | "
            f"{tr(lang, 'Статус', 'Status')}: {_status_label(row, lang)}"
        )

    header = tr(lang, f"👥 Все пользователи: {total}", f"👥 All users: {total}")
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
    text = (
        tr(lang, "📊 Статистика\n", "📊 Statistics\n")
        + f"{tr(lang, 'Пользователи', 'Users')}: {data['users']}\n"
        + f"{tr(lang, 'Новые за 24ч', 'New in 24h')}: {data['new_users_24h']}\n"
        + f"{tr(lang, 'Новые за 7д', 'New in 7d')}: {data['new_users_7d']}\n"
        + f"{tr(lang, 'Активные за 24ч', 'Active in 24h')}: {data['active_users_24h']}\n"
        + f"{tr(lang, 'Активные чаты', 'Active chats')}: {data['active_chats']}\n"
        + f"{tr(lang, 'Бот-чаты активные', 'Active bot chats')}: {data['active_virtual_chats']}\n"
        + f"{tr(lang, 'В очереди', 'In queue')}: {data['queue']}\n"
        + f"{tr(lang, 'Жалобы', 'Reports')}: {data['reports']}\n"
        + f"{tr(lang, 'Заблокированные', 'Blocked')}: {data['banned']}\n"
        + f"{tr(lang, 'Premium активные', 'Premium active')}: {data['premium_active']}\n"
        + f"{tr(lang, 'Premium покупатели', 'Premium buyers')}: {data['premium_buyers']}\n"
        + f"{tr(lang, 'Покупки premium', 'Premium purchases')}: {data['premium_purchases']}\n"
        + f"{tr(lang, 'Выручка Stars', 'Revenue Stars')}: {data['revenue_xtr']}\n"
        + f"{tr(lang, 'Используют ботов', 'Use virtual bots')}: {data['virtual_users']}\n"
        + f"{tr(lang, 'Промокоды', 'Promo codes')}: {data['promo_codes']}"
    )
    await message.answer(text)


@router.message(Command("export_stats"))
async def export_stats(message: Message, db: Database, config: Config) -> None:
    lang = await db.get_lang(message.from_user.id)
    if not _is_admin(message.from_user.id, config):
        await message.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."))
        return

    data = await db.stats()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["metric", "value"])
    writer.writerow(["users", data["users"]])
    writer.writerow(["new_users_24h", data["new_users_24h"]])
    writer.writerow(["new_users_7d", data["new_users_7d"]])
    writer.writerow(["active_users_24h", data["active_users_24h"]])
    writer.writerow(["active_chats", data["active_chats"]])
    writer.writerow(["active_virtual_chats", data["active_virtual_chats"]])
    writer.writerow(["queue", data["queue"]])
    writer.writerow(["reports", data["reports"]])
    writer.writerow(["banned", data["banned"]])
    writer.writerow(["engaged_users", data["engaged_users"]])
    writer.writerow(["premium_active", data["premium_active"]])
    writer.writerow(["premium_buyers", data["premium_buyers"]])
    writer.writerow(["premium_purchases", data["premium_purchases"]])
    writer.writerow(["revenue_xtr", data["revenue_xtr"]])
    writer.writerow(["virtual_users", data["virtual_users"]])
    writer.writerow(["promo_users", data["promo_users"]])
    writer.writerow(["promo_codes", data["promo_codes"]])

    content = buffer.getvalue().encode("utf-8")
    file = BufferedInputFile(content, filename="stats.csv")
    await message.answer_document(file)
