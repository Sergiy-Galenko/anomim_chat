from datetime import datetime, timezone, timedelta

from aiogram import F, Router
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from ...config import Config
from ...db.database import Database
from ..keyboards.main_menu import main_menu_keyboard
from ..keyboards.match_menu import searching_keyboard
from ..routers.match import _attempt_match
from ..utils.chat import end_chat, get_partner, safe_send_message
from ..utils.constants import SKIP_COOLDOWN_SECONDS, STATE_CHATTING, STATE_IDLE, STATE_SEARCHING
from ..utils.admin import is_admin
from ..utils.users import ensure_user, get_state, is_banned

router = Router()


@router.message(F.text == "🛑 Завершити діалог")
async def end_dialog(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)

    if await is_banned(db, user_id):
        await message.answer("Ваш акаунт заблоковано адміністрацією.")
        return

    state = await get_state(db, user_id)
    if state != STATE_CHATTING:
        await message.answer(
            "Активного діалогу немає.",
            reply_markup=main_menu_keyboard(is_admin=is_admin(user_id, config)),
        )
        return

    await end_chat(db, message.bot, user_id)


@router.message(F.text == "⏭ Скіп")
async def skip_partner(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)

    if await is_banned(db, user_id):
        return

    state = await get_state(db, user_id)
    if state != STATE_CHATTING:
        await message.answer(
            "Активного діалогу немає.",
            reply_markup=main_menu_keyboard(is_admin=is_admin(user_id, config)),
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
                    f"⏳ Зачекайте {remaining} сек перед наступним скіпом."
                )
                return
        except ValueError:
            pass

    now = datetime.now(timezone.utc)
    await db.set_skip_until(
        user_id, (now + timedelta(seconds=SKIP_COOLDOWN_SECONDS)).isoformat()
    )

    partner_id, _ = await get_partner(db, user_id)
    await end_chat(
        db,
        message.bot,
        user_id,
        notify_user=False,
        notify_partner=True,
        reason_text="⏭ Співрозмовника пропущено.",
    )
    if partner_id:
        await db.add_incident(user_id, partner_id, "skip", "")

    await db.set_state(user_id, STATE_SEARCHING)
    await db.add_to_queue(user_id)
    await message.answer("⏳ Шукаємо нового...", reply_markup=searching_keyboard())
    await _attempt_match(message, db, config, user_id)


@router.message(F.text == "🧷 Адмін: інфо партнера")
async def admin_partner_info(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)

    if not is_admin(user_id, config):
        await message.answer("Недостатньо прав.")
        return

    if await get_state(db, user_id) != STATE_CHATTING:
        await message.answer(
            "Ця функція доступна лише під час діалогу.",
            reply_markup=main_menu_keyboard(is_admin=True),
        )
        return

    partner_id, _ = await get_partner(db, user_id)
    if not partner_id:
        await message.answer("Партнер не знайдений.", reply_markup=main_menu_keyboard(is_admin=True))
        return

    try:
        chat = await message.bot.get_chat(partner_id)
        username = f"@{chat.username}" if getattr(chat, "username", None) else "—"
        name = " ".join([p for p in [chat.first_name, chat.last_name] if p]) or "Без імені"
        text = (
            "🧷 Інфо партнера\n"
            f"ID: {partner_id}\n"
            f"Username: {username}\n"
            f"Ім'я: {name}"
        )
    except Exception:
        text = f"🧷 Інфо партнера\nID: {partner_id}\nUsername: —\nІм'я: —"

    await message.answer(text, reply_markup=main_menu_keyboard(show_end=True, is_admin=True))


@router.message(F.text == "🚫 Адмін: бан партнера")
async def admin_ban_partner(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)

    if not is_admin(user_id, config):
        await message.answer("Недостатньо прав.")
        return

    if await get_state(db, user_id) != STATE_CHATTING:
        await message.answer(
            "Ця функція доступна лише під час діалогу.",
            reply_markup=main_menu_keyboard(is_admin=True),
        )
        return

    partner_id, _ = await get_partner(db, user_id)
    if not partner_id:
        await message.answer("Партнер не знайдений.", reply_markup=main_menu_keyboard(is_admin=True))
        return

    await db.set_banned(partner_id, True)
    await db.remove_from_queue(partner_id)
    await db.set_state(partner_id, STATE_IDLE)

    await end_chat(
        db,
        message.bot,
        user_id,
        reason_text="❌ Діалог завершено.",
    )
    await safe_send_message(message.bot, partner_id, "Ваш акаунт заблоковано.")
    await message.answer(
        f"Користувача {partner_id} заблоковано.",
        reply_markup=main_menu_keyboard(is_admin=True),
    )
    await db.add_incident(user_id, partner_id, "ban_partner", "")


def _sender_tag(message: Message) -> str:
    user = message.from_user
    if not user:
        return "👤 Невідомий"
    if user.username:
        name = f"@{user.username}"
    else:
        parts = [user.first_name or "", user.last_name or ""]
        name = " ".join([p for p in parts if p]).strip() or "Без імені"
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
        return

    state = await get_state(db, user_id)
    if state != STATE_CHATTING:
        # Ignore unrelated messages when not chatting.
        return

    partner_id, _ = await get_partner(db, user_id)
    if not partner_id:
        await db.set_state(user_id, STATE_IDLE)
        await message.answer(
            "Діалог не знайдено.",
            reply_markup=main_menu_keyboard(is_admin=is_admin(user_id, config)),
        )
        return

    show_sender = is_admin(partner_id, config)
    tag = _sender_tag(message) if show_sender else ""

    try:
        if message.text:
            text = f"{tag}\n{message.text}" if show_sender else message.text
            await message.bot.send_message(partner_id, text)
        elif message.photo:
            caption = _merge_caption(tag, message.caption) if show_sender else message.caption
            await message.bot.send_photo(
                partner_id, message.photo[-1].file_id, caption=caption
            )
        elif message.video:
            caption = _merge_caption(tag, message.caption) if show_sender else message.caption
            await message.bot.send_video(partner_id, message.video.file_id, caption=caption)
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
            caption = _merge_caption(tag, message.caption) if show_sender else message.caption
            await message.bot.send_document(
                partner_id, message.document.file_id, caption=caption
            )
        else:
            await message.bot.send_message(partner_id, "Непідтримуваний тип повідомлення.")
    except (TelegramForbiddenError, TelegramBadRequest):
        # Partner is unavailable: end the chat for the sender.
        await end_chat(
            db,
            message.bot,
            user_id,
            notify_partner=False,
            reason_text="Партнер недоступний. Спробуйте ще раз.",
        )
