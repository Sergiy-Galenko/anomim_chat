from aiogram import F, Router
from aiogram.types import Message

from ...config import Config
from ...db.database import Database
from ..keyboards.main_menu import main_menu_keyboard
from ..keyboards.match_menu import searching_keyboard
from ..utils.chat import end_chat, safe_send_message
from ..utils.constants import STATE_CHATTING, STATE_IDLE, STATE_SEARCHING
from ..utils.admin import is_admin
from ..utils.users import ensure_user, get_state, is_banned

router = Router()


@router.message(F.text.in_({"🔍 Знайти співрозмовника", "🔍 Знайти нового"}))
async def find_partner(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)

    if await is_banned(db, user_id):
        await message.answer("Ваш акаунт заблоковано адміністрацією.")
        return

    state = await get_state(db, user_id)
    if state == STATE_CHATTING:
        await message.answer(
            "У вас вже є активний діалог. Завершіть його, щоб шукати нового.",
            reply_markup=main_menu_keyboard(show_end=True, is_admin=is_admin(user_id, config)),
        )
        return

    if state == STATE_SEARCHING:
        await message.answer("Ви вже у пошуку...", reply_markup=searching_keyboard())
        return

    await db.set_state(user_id, STATE_SEARCHING)
    await db.add_to_queue(user_id)
    await message.answer("⏳ Шукаємо...", reply_markup=searching_keyboard())

    # Try to match with another waiting user with same interest.
    async with db.lock:
        # Ensure the user is still searching before matching.
        current_state = await get_state(db, user_id)
        if current_state != STATE_SEARCHING:
            return

        interest = (await db.get_interests(user_id)).strip()
        candidate_id = await db.get_queue_candidate_by_interest(user_id, interest)
        if not candidate_id:
            return

        await db.remove_from_queue(user_id)
        await db.remove_from_queue(candidate_id)
        await db.set_state(user_id, STATE_CHATTING)
        await db.set_state(candidate_id, STATE_CHATTING)
        await db.create_pair(user_id, candidate_id)
        await db.increment_chats(user_id)
        await db.increment_chats(candidate_id)

    text = "✅ Співрозмовника знайдено. Пиши повідомлення."
    sent_user = await safe_send_message(
        message.bot,
        user_id,
        text,
        reply_markup=main_menu_keyboard(show_end=True, is_admin=is_admin(user_id, config)),
    )
    sent_candidate = await safe_send_message(
        message.bot,
        candidate_id,
        text,
        reply_markup=main_menu_keyboard(
            show_end=True, is_admin=is_admin(candidate_id, config)
        ),
    )

    if not sent_user or not sent_candidate:
        # If one user is unavailable, end the chat for the other.
        await end_chat(
            db,
            message.bot,
            user_id if sent_user else candidate_id,
            reason_text="Партнер недоступний. Спробуйте ще раз.",
        )


@router.message(F.text == "❌ Скасувати пошук")
async def cancel_search(message: Message, db: Database, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)

    if await is_banned(db, user_id):
        await message.answer("Ваш акаунт заблоковано адміністрацією.")
        return

    state = await get_state(db, user_id)
    if state != STATE_SEARCHING:
        await message.answer(
            "Ви зараз не в пошуку.",
            reply_markup=main_menu_keyboard(is_admin=is_admin(user_id, config)),
        )
        return

    await db.remove_from_queue(user_id)
    await db.set_state(user_id, STATE_IDLE)
    await message.answer(
        "Пошук скасовано.",
        reply_markup=main_menu_keyboard(is_admin=is_admin(user_id, config)),
    )
