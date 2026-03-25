from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from ...config import Config
from ...db.database import Database
from ..keyboards.main_menu import main_menu_keyboard
from ..keyboards.match_menu import find_new_keyboard, searching_keyboard
from ..routers.match import _attempt_match
from ..utils.chat import (
    end_chat,
    get_partner,
    safe_edit_message_reply_markup,
    safe_send_message,
)
from ..utils.content_filter import contains_blocked_content
from ..utils.constants import SKIP_COOLDOWN_SECONDS, STATE_CHATTING, STATE_IDLE, STATE_SEARCHING
from ..utils.i18n import any_button, tr
from ..utils.admin import is_admin
from ..utils.users import (
    ensure_user,
    format_until_text,
    get_active_restrictions_from_snapshot,
    get_lang_from_snapshot,
    get_state_from_snapshot,
    get_user_snapshot,
    is_banned_from_snapshot,
    is_muted_from_snapshot,
)
from ..utils.virtual_companions import (
    build_virtual_admin_text,
    is_virtual_companion,
    send_virtual_reply_with_memory,
    virtual_variant_label,
)

router = Router()


@router.message(F.text.in_(any_button("end_dialog")))
async def end_dialog(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)
    user = await get_user_snapshot(db, user_id)
    lang = get_lang_from_snapshot(user)

    if is_banned_from_snapshot(user):
        await message.answer(
            tr(
                lang,
                "Ваш аккаунт заблокирован администрацией.",
                "Your account is blocked by administration.",
                "Ваш акаунт заблоковано адміністрацією.",
                "Dein Konto wurde von der Administration gesperrt.",
            )
        )
        return

    state = get_state_from_snapshot(user)
    if state != STATE_CHATTING:
        await message.answer(
            tr(lang, "Активного диалога нет.", "No active chat.", "Активного діалогу немає.", "Kein aktiver Chat."),
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
        reason_uk="❌ Діалог завершено.",
        reason_de="❌ Chat beendet.",
    )
    await _maybe_auto_search(message, db, config, user_id)
    if partner_id:
        await _maybe_auto_search(message, db, config, partner_id)


@router.message(F.text.in_(any_button("skip")))
async def skip_partner(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)
    user = await get_user_snapshot(db, user_id)
    lang = get_lang_from_snapshot(user)

    if is_banned_from_snapshot(user):
        await message.answer(
            tr(
                lang,
                "Ваш аккаунт заблокирован администрацией.",
                "Your account is blocked by administration.",
                "Ваш акаунт заблоковано адміністрацією.",
                "Dein Konto wurde von der Administration gesperrt.",
            )
        )
        return

    state = get_state_from_snapshot(user)
    if state != STATE_CHATTING:
        await message.answer(
            tr(lang, "Активного диалога нет.", "No active chat.", "Активного діалогу немає.", "Kein aktiver Chat."),
            reply_markup=main_menu_keyboard(
                is_admin=is_admin(user_id, config),
                lang=lang,
            ),
        )
        return

    skip_until_raw = user["skip_until"] or ""
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
                        f"⏳ Зачекайте {remaining} с перед наступним пропуском.",
                        f"⏳ Warte {remaining} Sek. vor dem nächsten Überspringen.",
                    )
                )
                return
        except ValueError:
            pass

    now = datetime.now(timezone.utc)
    result = await db.skip_chat_session(
        user_id,
        skip_until=(now + timedelta(seconds=SKIP_COOLDOWN_SECONDS)).isoformat(),
    )
    if result is None:
        await message.answer(
            tr(lang, "Активного диалога нет.", "No active chat.", "Активного діалогу немає.", "Kein aktiver Chat."),
            reply_markup=main_menu_keyboard(
                is_admin=is_admin(user_id, config),
                lang=lang,
            ),
        )
        return

    partner_id = None if result.partner_is_virtual else result.partner_id
    if partner_id:
        partner_lang = await db.get_lang(partner_id)
        await safe_send_message(
            message.bot,
            partner_id,
            tr(
                partner_lang,
                "⏭ Собеседник пропустил диалог.",
                "⏭ Partner skipped the chat.",
                "⏭ Співрозмовник пропустив діалог.",
                "⏭ Gesprächspartner hat den Chat übersprungen.",
            ),
            reply_markup=find_new_keyboard(partner_lang),
        )

    await message.answer(
        tr(lang, "⏳ Ищем нового...", "⏳ Looking for a new partner...", "⏳ Шукаємо нового...", "⏳ Suche einen neuen Gesprächspartner..."),
        reply_markup=searching_keyboard(lang),
    )
    await _attempt_match(message, db, config, user_id)


@router.message(F.text.in_(any_button("admin_partner_info")))
async def admin_partner_info(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)
    user = await get_user_snapshot(db, user_id)
    lang = get_lang_from_snapshot(user)

    if not is_admin(user_id, config):
        await message.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."))
        return

    if get_state_from_snapshot(user) != STATE_CHATTING:
        await message.answer(
            tr(
                lang,
                "Эта функция доступна только во время диалога.",
                "This feature is available only during an active chat.",
            ),
            reply_markup=main_menu_keyboard(is_admin=True, lang=lang),
        )
        return

    partner_id, pair_id = await get_partner(db, user_id)
    if not partner_id:
        await message.answer(
            tr(lang, "Собеседник не найден.", "Partner not found."),
            reply_markup=main_menu_keyboard(is_admin=True, lang=lang),
        )
        return

    if is_virtual_companion(partner_id):
        variant_line = ""
        if pair_id:
            ab_session = await db.get_virtual_ab_session(pair_id)
            if ab_session:
                variant_line = (
                    "\n"
                    + tr(lang, "A/B режим", "A/B mode")
                    + f": {virtual_variant_label(ab_session['variant_key'], lang)}"
                )
        await message.answer(
            build_virtual_admin_text(partner_id, lang) + variant_line,
            reply_markup=main_menu_keyboard(show_end=True, is_admin=True, lang=lang),
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
    user = await get_user_snapshot(db, user_id)
    lang = get_lang_from_snapshot(user)

    if not is_admin(user_id, config):
        await message.answer(tr(lang, "Недостаточно прав.", "Insufficient permissions."))
        return

    if get_state_from_snapshot(user) != STATE_CHATTING:
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

    if is_virtual_companion(partner_id):
        await message.answer(
            tr(
                lang,
                "Встроенную виртуальную собеседницу нельзя заблокировать.",
                "The built-in virtual companion can't be banned.",
            ),
            reply_markup=main_menu_keyboard(show_end=True, is_admin=True, lang=lang),
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
        reason_uk="❌ Діалог завершено.",
        reason_de="❌ Chat beendet.",
    )
    await safe_send_message(
        message.bot,
        partner_id,
        tr(
            partner_lang,
            "Ваш аккаунт заблокирован.",
            "Your account has been blocked.",
            "Ваш акаунт заблоковано.",
            "Dein Konto wurde gesperrt.",
        ),
    )
    await message.answer(
        tr(
            lang,
            f"Пользователь {partner_id} заблокирован.",
            f"User {partner_id} has been blocked.",
            f"Користувача {partner_id} заблоковано.",
            f"Benutzer {partner_id} wurde gesperrt.",
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


async def _archive_media_message(
    db: Database,
    sender_id: int,
    receiver_id: int,
    message: Message,
) -> None:
    if message.photo:
        await db.add_media_record(
            sender_id=sender_id,
            receiver_id=receiver_id,
            media_type="photo",
            file_id=message.photo[-1].file_id,
            caption=message.caption or "",
        )
    elif message.video:
        await db.add_media_record(
            sender_id=sender_id,
            receiver_id=receiver_id,
            media_type="video",
            file_id=message.video.file_id,
            caption=message.caption or "",
        )
    elif message.animation:
        await db.add_media_record(
            sender_id=sender_id,
            receiver_id=receiver_id,
            media_type="animation",
            file_id=message.animation.file_id,
            caption=message.caption or "",
        )
    elif message.audio:
        await db.add_media_record(
            sender_id=sender_id,
            receiver_id=receiver_id,
            media_type="audio",
            file_id=message.audio.file_id,
            caption=message.caption or "",
        )
    elif message.voice:
        await db.add_media_record(
            sender_id=sender_id,
            receiver_id=receiver_id,
            media_type="voice",
            file_id=message.voice.file_id,
        )
    elif message.video_note:
        await db.add_media_record(
            sender_id=sender_id,
            receiver_id=receiver_id,
            media_type="video_note",
            file_id=message.video_note.file_id,
        )
    elif message.sticker:
        await db.add_media_record(
            sender_id=sender_id,
            receiver_id=receiver_id,
            media_type="sticker",
            file_id=message.sticker.file_id,
        )
    elif message.document:
        await db.add_media_record(
            sender_id=sender_id,
            receiver_id=receiver_id,
            media_type="document",
            file_id=message.document.file_id,
            caption=message.caption or "",
        )


def _virtual_memory_text(message: Message) -> str:
    if message.text:
        return message.text
    if message.photo:
        return f"[photo] {message.caption or ''}".strip()
    if message.video:
        return f"[video] {message.caption or ''}".strip()
    if message.animation:
        return f"[animation] {message.caption or ''}".strip()
    if message.audio:
        return f"[audio] {message.caption or ''}".strip()
    if message.voice:
        return "[voice]"
    if message.video_note:
        return "[video_note]"
    if message.sticker:
        return "[sticker]"
    if message.document:
        return f"[document] {message.caption or ''}".strip()
    return ""


def _message_has_media(message: Message) -> bool:
    return any(
        (
            message.photo,
            message.video,
            message.animation,
            message.audio,
            message.voice,
            message.video_note,
            message.sticker,
            message.document,
        )
    )


def _filterable_text(message: Message) -> str:
    return (message.text or message.caption or "").strip()


@router.message()
async def relay_message(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)
    user = await get_user_snapshot(db, user_id)
    user_lang = get_lang_from_snapshot(user)

    if is_banned_from_snapshot(user):
        await message.answer(
            tr(
                user_lang,
                "Ваш аккаунт заблокирован администрацией.",
                "Your account is blocked by administration.",
                "Ваш акаунт заблоковано адміністрацією.",
                "Dein Konto wurde von der Administration gesperrt.",
            )
        )
        return

    state = get_state_from_snapshot(user)
    if state != STATE_CHATTING:
        # Ignore unrelated messages when not chatting.
        return

    if is_muted_from_snapshot(user):
        _, muted_until = get_active_restrictions_from_snapshot(user)
        until_text = format_until_text(muted_until)
        await message.answer(
            tr(
                user_lang,
                f"🔇 Вы в муте до {until_text}. Отправка сообщений временно недоступна.",
                f"🔇 You are muted until {until_text}. Sending messages is temporarily disabled.",
                f"🔇 Ви в муті до {until_text}. Надсилання повідомлень тимчасово недоступне.",
                f"🔇 Du bist bis {until_text} stummgeschaltet. Das Senden von Nachrichten ist vorübergehend deaktiviert.",
            )
        )
        return

    partner_id, pair_id = await get_partner(db, user_id)
    if not partner_id:
        await db.set_state(user_id, STATE_IDLE)
        await message.answer(
            tr(user_lang, "Диалог не найден.", "Chat not found.", "Діалог не знайдено.", "Chat nicht gefunden."),
            reply_markup=main_menu_keyboard(
                is_admin=is_admin(user_id, config),
                lang=user_lang,
            ),
        )
        return

    if is_virtual_companion(partner_id):
        await _archive_media_message(db, user_id, partner_id, message)
        variant_key: str | None = None
        if pair_id:
            ab_session = await db.get_virtual_ab_session(pair_id)
            variant_key = (ab_session["variant_key"] or "").strip() if ab_session else None
            await db.increment_virtual_ab_user_message(
                pair_id,
                is_media=_message_has_media(message),
            )
            await db.add_virtual_memory(
                pair_id=pair_id,
                user_id=user_id,
                companion_id=partner_id,
                speaker="user",
                content=_virtual_memory_text(message),
            )
            memory = await db.get_virtual_memory(pair_id, limit=10)
        else:
            memory = []
        reply_text = await send_virtual_reply_with_memory(
            message.bot,
            user_id,
            partner_id,
            message,
            user_lang,
            memory=memory,
            variant_key=variant_key,
        )
        if pair_id and reply_text:
            await db.increment_virtual_ab_companion_message(pair_id)
            await db.add_virtual_memory(
                pair_id=pair_id,
                user_id=user_id,
                companion_id=partner_id,
                speaker="companion",
                content=reply_text,
            )
        return

    partner = await db.get_user_snapshot(partner_id)
    partner_lang = get_lang_from_snapshot(partner)
    if partner and bool(partner["content_filter"]) and contains_blocked_content(_filterable_text(message)):
        await message.answer(
            tr(
                user_lang,
                "Сообщение заблокировано фильтром контента собеседника.",
                "Your message was blocked by your partner's content filter.",
            )
        )
        return

    show_sender = is_admin(partner_id, config)
    tag = _sender_tag(message, partner_lang) if show_sender else ""
    try:
        if message.text:
            text = f"{tag}\n{message.text}" if show_sender else message.text
            await message.bot.send_message(partner_id, text)
        elif message.photo:
            caption = _merge_caption(tag, message.caption) if show_sender else message.caption
            await message.bot.send_photo(
                partner_id, message.photo[-1].file_id, caption=caption
            )
            await _archive_media_message(db, user_id, partner_id, message)
        elif message.video:
            caption = _merge_caption(tag, message.caption) if show_sender else message.caption
            await message.bot.send_video(partner_id, message.video.file_id, caption=caption)
            await _archive_media_message(db, user_id, partner_id, message)
        elif message.animation:
            caption = _merge_caption(tag, message.caption) if show_sender else message.caption
            await message.bot.send_animation(partner_id, message.animation.file_id, caption=caption)
            await _archive_media_message(db, user_id, partner_id, message)
        elif message.audio:
            caption = _merge_caption(tag, message.caption) if show_sender else message.caption
            await message.bot.send_audio(partner_id, message.audio.file_id, caption=caption)
            await _archive_media_message(db, user_id, partner_id, message)
        elif message.voice:
            if show_sender:
                await message.bot.send_message(partner_id, tag)
            await message.bot.send_voice(partner_id, message.voice.file_id)
            await _archive_media_message(db, user_id, partner_id, message)
        elif message.video_note:
            if show_sender:
                await message.bot.send_message(partner_id, tag)
            await message.bot.send_video_note(partner_id, message.video_note.file_id)
            await _archive_media_message(db, user_id, partner_id, message)
        elif message.sticker:
            if show_sender:
                await message.bot.send_message(partner_id, tag)
            await message.bot.send_sticker(partner_id, message.sticker.file_id)
            await _archive_media_message(db, user_id, partner_id, message)
        elif message.document:
            caption = _merge_caption(tag, message.caption) if show_sender else message.caption
            await message.bot.send_document(
                partner_id, message.document.file_id, caption=caption
            )
            await _archive_media_message(db, user_id, partner_id, message)
        else:
            await message.bot.send_message(
                partner_id,
                tr(partner_lang, "Неподдерживаемый тип сообщения.", "Unsupported message type."),
            )
    except (TelegramForbiddenError, TelegramBadRequest):
        # Partner is unavailable: end the chat for the sender.
        await end_chat(
            db,
            message.bot,
            user_id,
            notify_partner=False,
            collect_feedback=False,
            reason_ru="Собеседник недоступен. Попробуйте еще раз.",
            reason_en="Partner is unavailable. Please try again.",
            reason_uk="Співрозмовник недоступний. Спробуйте ще раз.",
            reason_de="Gesprächspartner ist nicht verfügbar. Bitte versuche es erneut.",
        )


async def _maybe_auto_search(message: Message, db: Database, config: Config, target_user_id: int) -> None:
    if not await db.get_auto_search(target_user_id):
        return
    user = await db.get_user_snapshot(target_user_id)
    if is_banned_from_snapshot(user):
        return

    state = get_state_from_snapshot(user)
    if state in {STATE_CHATTING, STATE_SEARCHING}:
        return

    await db.queue_user_for_search(target_user_id)
    lang = get_lang_from_snapshot(user)
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
