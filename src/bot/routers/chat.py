from datetime import datetime, timezone, timedelta

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from ...config import Config
from ...db.database import Database
from ..keyboards.main_menu import main_menu_keyboard
from ..keyboards.match_menu import searching_keyboard
from ..routers.match import _attempt_match
from ..utils.chat import (
    end_chat,
    get_partner,
    safe_edit_message_reply_markup,
    safe_send_message,
)
from ..utils.constants import SKIP_COOLDOWN_SECONDS, STATE_CHATTING, STATE_IDLE, STATE_SEARCHING
from ..utils.content_filter import contains_blocked_content
from ..utils.i18n import any_button, tr
from ..utils.admin import is_admin
from ..utils.users import ensure_user, format_until_text, get_active_restrictions, get_state, is_banned, is_muted

router = Router()


@router.message(F.text.in_(any_button("end_dialog")))
async def end_dialog(message: Message, db: Database, config: Config) -> None:
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

    state = await get_state(db, user_id)
    if state != STATE_CHATTING:
        await message.answer(
            tr(lang, "Активного диалога нет.", "No active chat."),
            reply_markup=main_menu_keyboard(
                is_admin=is_admin(user_id, config),
                lang=lang,
            ),
        )
        return

    partner_id = await end_chat(
        db,
        message.bot,
        user_id,
        reason_ru="❌ Диалог завершен.",
        reason_en="❌ Chat ended.",
    )
    await _maybe_auto_search(message, db, config, user_id)
    if partner_id:
        await _maybe_auto_search(message, db, config, partner_id)


@router.message(F.text.in_(any_button("skip")))
async def skip_partner(message: Message, db: Database, config: Config) -> None:
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

    state = await get_state(db, user_id)
    if state != STATE_CHATTING:
        await message.answer(
            tr(lang, "Активного диалога нет.", "No active chat."),
            reply_markup=main_menu_keyboard(
                is_admin=is_admin(user_id, config),
                lang=lang,
            ),
        )
        return

    skip_until_raw = await db.get_skip_until(user_id)
    if skip_until_raw:
        try:
            skip_until = datetime.fromisoformat(skip_until_raw)
            if skip_until.tzinfo is None:
                skip_until = skip_until.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if skip_until > now:
                remaining = int((skip_until - now).total_seconds())
                await message.answer(
                    tr(
                        lang,
                        f"⏳ Подождите {remaining} сек перед следующим пропуском.",
                        f"⏳ Wait {remaining} sec before the next skip.",
                    )
                )
                return
        except ValueError:
            pass

    now = datetime.now(timezone.utc)
    await db.set_skip_until(
        user_id, (now + timedelta(seconds=SKIP_COOLDOWN_SECONDS)).isoformat()
    )

    partner_id, _ = await get_partner(db, user_id)
    partner_lang = await db.get_lang(partner_id) if partner_id else lang
    await end_chat(
        db,
        message.bot,
        user_id,
        notify_user=False,
        notify_partner=True,
        reason_ru="⏭ Собеседник пропустил диалог.",
        reason_en="⏭ Partner skipped the chat.",
    )
    if partner_id:
        await db.add_incident(user_id, partner_id, "skip", "")

    await db.set_state(user_id, STATE_SEARCHING)
    await db.add_to_queue(user_id)
    await message.answer(
        tr(lang, "⏳ Ищем нового...", "⏳ Looking for a new partner..."),
        reply_markup=searching_keyboard(lang),
    )
    await _attempt_match(message, db, config, user_id)


@router.message(F.text.in_(any_button("admin_partner_info")))
async def admin_partner_info(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)
    lang = await db.get_lang(user_id)

    if not is_admin(user_id, config):
        await message.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."))
        return

    if await get_state(db, user_id) != STATE_CHATTING:
        await message.answer(
            tr(
                lang,
                "Эта функция доступна только во время диалога.",
                "This feature is available only during an active chat.",
            ),
            reply_markup=main_menu_keyboard(is_admin=True, lang=lang),
        )
        return

    partner_id, _ = await get_partner(db, user_id)
    if not partner_id:
        await message.answer(
            tr(lang, "Собеседник не найден.", "Partner not found."),
            reply_markup=main_menu_keyboard(is_admin=True, lang=lang),
        )
        return

    try:
        chat = await message.bot.get_chat(partner_id)
        username = f"@{chat.username}" if getattr(chat, "username", None) else "—"
        name = " ".join([p for p in [chat.first_name, chat.last_name] if p]) or tr(
            lang, "Без имени", "No name"
        )
        text = (
            tr(lang, "🧷 Инфо партнера\n", "🧷 Partner info\n")
            + f"ID: {partner_id}\n"
            f"Username: {username}\n"
            f"{tr(lang, 'Имя', 'Name')}: {name}"
        )
    except Exception:
        text = (
            tr(lang, "🧷 Инфо партнера\n", "🧷 Partner info\n")
            + f"ID: {partner_id}\nUsername: —\n{tr(lang, 'Имя', 'Name')}: —"
        )

    await message.answer(
        text,
        reply_markup=main_menu_keyboard(show_end=True, is_admin=True, lang=lang),
    )


@router.message(F.text.in_(any_button("admin_ban_partner")))
async def admin_ban_partner(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)
    lang = await db.get_lang(user_id)

    if not is_admin(user_id, config):
        await message.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."))
        return

    if await get_state(db, user_id) != STATE_CHATTING:
        await message.answer(
            tr(
                lang,
                "Эта функция доступна только во время диалога.",
                "This feature is available only during an active chat.",
            ),
            reply_markup=main_menu_keyboard(is_admin=True, lang=lang),
        )
        return

    partner_id, _ = await get_partner(db, user_id)
    if not partner_id:
        await message.answer(
            tr(lang, "Собеседник не найден.", "Partner not found."),
            reply_markup=main_menu_keyboard(is_admin=True, lang=lang),
        )
        return

    await db.set_banned(partner_id, True)
    await db.remove_from_queue(partner_id)
    await db.set_state(partner_id, STATE_IDLE)
    partner_lang = await db.get_lang(partner_id)

    await end_chat(
        db,
        message.bot,
        user_id,
        collect_feedback=False,
        reason_ru="❌ Диалог завершен.",
        reason_en="❌ Chat ended.",
    )
    await safe_send_message(
        message.bot,
        partner_id,
        tr(
            partner_lang,
            "Ваш аккаунт заблокирован.",
            "Your account has been blocked.",
        ),
    )
    await message.answer(
        tr(
            lang,
            f"Пользователь {partner_id} заблокирован.",
            f"User {partner_id} has been blocked.",
        ),
        reply_markup=main_menu_keyboard(is_admin=True, lang=lang),
    )
    await db.add_incident(user_id, partner_id, "ban_partner", "")


@router.callback_query(F.data.in_({"rate:up", "rate:down"}))
async def rate_partner(callback: CallbackQuery, db: Database) -> None:
    user_id = callback.from_user.id
    await ensure_user(db, user_id)

    value = 1 if callback.data == "rate:up" else -1
    success, _ = await db.submit_rating(user_id, value)
    lang = await db.get_lang(user_id)

    if not success:
        await callback.answer(
            tr(lang, "Оценка уже выставлена или недоступна.", "Rating is no longer available."),
            show_alert=True,
        )
        return

    if callback.message:
        await safe_edit_message_reply_markup(callback.message, reply_markup=None)

    await callback.answer(tr(lang, "Оценка сохранена.", "Rating saved."))
    if callback.message:
        await callback.message.answer(
            tr(lang, "Спасибо за отзыв.", "Thanks for your feedback.")
        )


def _sender_tag(message: Message, lang: str) -> str:
    user = message.from_user
    if not user:
        return tr(lang, "👤 Неизвестный", "👤 Unknown")
    if user.username:
        name = f"@{user.username}"
    else:
        parts = [user.first_name or "", user.last_name or ""]
        name = " ".join([p for p in parts if p]).strip() or tr(lang, "Без имени", "No name")
    return f"👤 {name} (ID: {user.id})"


def _merge_caption(tag: str, caption: str | None) -> str:
    if caption:
        return f"{tag}\n{caption}"
    return tag


@router.message()
async def relay_message(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)

    if await is_banned(db, user_id):
        lang = await db.get_lang(user_id)
        await message.answer(
            tr(
                lang,
                "Ваш аккаунт заблокирован администрацией.",
                "Your account is blocked by administration.",
            )
        )
        return

    state = await get_state(db, user_id)
    if state != STATE_CHATTING:
        # Ignore unrelated messages when not chatting.
        return

    if await is_muted(db, user_id):
        lang = await db.get_lang(user_id)
        _, muted_until = await get_active_restrictions(db, user_id)
        until_text = format_until_text(muted_until)
        await message.answer(
            tr(
                lang,
                f"🔇 Вы в муте до {until_text}. Отправка сообщений временно недоступна.",
                f"🔇 You are muted until {until_text}. Sending messages is temporarily disabled.",
            )
        )
        return

    partner_id, _ = await get_partner(db, user_id)
    if not partner_id:
        await db.set_state(user_id, STATE_IDLE)
        lang = await db.get_lang(user_id)
        await message.answer(
            tr(lang, "Диалог не найден.", "Chat not found."),
            reply_markup=main_menu_keyboard(
                is_admin=is_admin(user_id, config),
                lang=lang,
            ),
        )
        return

    show_sender = is_admin(partner_id, config)
    partner_lang = await db.get_lang(partner_id)
    tag = _sender_tag(message, partner_lang) if show_sender else ""
    content_filter_enabled = await db.get_content_filter(user_id)

    try:
        if message.text:
            if content_filter_enabled and contains_blocked_content(message.text):
                lang = await db.get_lang(user_id)
                await message.answer(
                    tr(
                        lang,
                        "Сообщение не отправлено: сработал фильтр контента.",
                        "Message blocked by content filter.",
                    )
                )
                await db.add_incident(user_id, partner_id, "content_block", "text")
                return
            text = f"{tag}\n{message.text}" if show_sender else message.text
            await message.bot.send_message(partner_id, text)
        elif message.photo:
            if content_filter_enabled and contains_blocked_content(message.caption or ""):
                lang = await db.get_lang(user_id)
                await message.answer(
                    tr(
                        lang,
                        "Подпись к фото заблокирована фильтром контента.",
                        "Photo caption blocked by content filter.",
                    )
                )
                await db.add_incident(user_id, partner_id, "content_block", "photo_caption")
                return
            caption = _merge_caption(tag, message.caption) if show_sender else message.caption
            await message.bot.send_photo(
                partner_id, message.photo[-1].file_id, caption=caption
            )
            await db.add_media_record(
                sender_id=user_id,
                receiver_id=partner_id,
                media_type="photo",
                file_id=message.photo[-1].file_id,
                caption=message.caption or "",
            )
        elif message.video:
            if content_filter_enabled and contains_blocked_content(message.caption or ""):
                lang = await db.get_lang(user_id)
                await message.answer(
                    tr(
                        lang,
                        "Подпись к видео заблокирована фильтром контента.",
                        "Video caption blocked by content filter.",
                    )
                )
                await db.add_incident(user_id, partner_id, "content_block", "video_caption")
                return
            caption = _merge_caption(tag, message.caption) if show_sender else message.caption
            await message.bot.send_video(partner_id, message.video.file_id, caption=caption)
            await db.add_media_record(
                sender_id=user_id,
                receiver_id=partner_id,
                media_type="video",
                file_id=message.video.file_id,
                caption=message.caption or "",
            )
        elif message.voice:
            if show_sender:
                await message.bot.send_message(partner_id, tag)
            await message.bot.send_voice(partner_id, message.voice.file_id)
        elif message.video_note:
            if show_sender:
                await message.bot.send_message(partner_id, tag)
            await message.bot.send_video_note(partner_id, message.video_note.file_id)
        elif message.sticker:
            if show_sender:
                await message.bot.send_message(partner_id, tag)
            await message.bot.send_sticker(partner_id, message.sticker.file_id)
        elif message.document:
            if content_filter_enabled and contains_blocked_content(message.caption or ""):
                lang = await db.get_lang(user_id)
                await message.answer(
                    tr(
                        lang,
                        "Подпись к документу заблокирована фильтром контента.",
                        "Document caption blocked by content filter.",
                    )
                )
                await db.add_incident(user_id, partner_id, "content_block", "document_caption")
                return
            caption = _merge_caption(tag, message.caption) if show_sender else message.caption
            await message.bot.send_document(
                partner_id, message.document.file_id, caption=caption
            )
        else:
            await message.bot.send_message(
                partner_id,
                tr(partner_lang, "Неподдерживаемый тип сообщения.", "Unsupported message type."),
            )
    except (TelegramForbiddenError, TelegramBadRequest):
        # Partner is unavailable: end the chat for the sender.
        lang = await db.get_lang(user_id)
        await end_chat(
            db,
            message.bot,
            user_id,
            notify_partner=False,
            collect_feedback=False,
            reason_ru="Собеседник недоступен. Попробуйте еще раз.",
            reason_en="Partner is unavailable. Please try again.",
        )


async def _maybe_auto_search(message: Message, db: Database, config: Config, target_user_id: int) -> None:
    if not await db.get_auto_search(target_user_id):
        return
    if await is_banned(db, target_user_id):
        return

    state = await get_state(db, target_user_id)
    if state in {STATE_CHATTING, STATE_SEARCHING}:
        return

    await db.set_state(target_user_id, STATE_SEARCHING)
    await db.add_to_queue(target_user_id)
    lang = await db.get_lang(target_user_id)
    await safe_send_message(
        message.bot,
        target_user_id,
        tr(
            lang,
            "🔁 Автопоиск включен. Ищем нового собеседника...",
            "🔁 Auto-search enabled. Looking for a new partner...",
        ),
        reply_markup=searching_keyboard(lang),
    )
    await _attempt_match(message, db, config, target_user_id)
