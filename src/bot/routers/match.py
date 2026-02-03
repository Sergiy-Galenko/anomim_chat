from aiogram import F, Router
from aiogram.types import Message

from ...config import Config
from ...db.database import Database
from ..keyboards.main_menu import main_menu_keyboard
from ..keyboards.match_menu import searching_keyboard
from ..utils.chat import end_chat, safe_send_message
from ..utils.constants import STATE_CHATTING, STATE_IDLE, STATE_SEARCHING
from ..utils.admin import is_admin
from ..utils.interests import parse_interests
from ..utils.premium import is_premium_until
from ..utils.users import ensure_user, get_state, is_banned

router = Router()


@router.message(
    F.text.in_(
        {
            "🔍 Знайти співрозмовника",
            "🔍 Пошук співрозмовника",
            "🔍 Знайти нового",
            "🔄 Знайти нового",
        }
    )
)
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

    await _attempt_match(message, db, config, user_id)


async def _attempt_match(message: Message, db: Database, config: Config, user_id: int) -> bool:
    # Try to match with another waiting user based on interests.
    async with db.lock:
        # Ensure the user is still searching before matching.
        current_state = await get_state(db, user_id)
        if current_state != STATE_SEARCHING:
            return False

        raw_interests = (await db.get_interests(user_id)).strip()
        user_interests = set(parse_interests(raw_interests))
        premium_until = await db.get_premium_until(user_id)
        user_is_premium = is_premium_until(premium_until)
        user_only_interest = await db.get_only_interest(user_id) and user_is_premium

        candidates = await db.get_queue_candidates(user_id)
        candidate_id = _pick_candidate(user_interests, user_only_interest, candidates)
        if not candidate_id:
            return False

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
        return False

    return True


def _pick_candidate(
    user_interests: set[str],
    user_only: bool,
    candidates,
) -> int | None:
    if user_only and not user_interests:
        return None
    # First pass: prefer users with intersecting interests.
    matched_premium: list[int] = []
    matched_regular: list[int] = []
    for row in candidates:
        cand_interests = set(parse_interests(row["interests"] or ""))
        cand_premium = is_premium_until(row["premium_until"] or "")
        cand_only = bool(row["only_interest"]) and cand_premium
        if _has_intersection(user_interests, cand_interests):
            if cand_premium:
                matched_premium.append(int(row["user_id"]))
            else:
                matched_regular.append(int(row["user_id"]))
        elif cand_only:
            # Candidate requires interest match; skip in fallback.
            continue

    if matched_premium:
        return matched_premium[0]
    if matched_regular:
        return matched_regular[0]

    # Fallback: only if not strict and user doesn't require interest.
    if user_only:
        return None

    fallback_premium: list[int] = []
    fallback_regular: list[int] = []
    for row in candidates:
        cand_premium = is_premium_until(row["premium_until"] or "")
        cand_only = bool(row["only_interest"]) and cand_premium
        if cand_only:
            continue
        if not user_interests:
            if cand_premium:
                fallback_premium.append(int(row["user_id"]))
            else:
                fallback_regular.append(int(row["user_id"]))
        else:
            # User has interests but allows broad search.
            if cand_premium:
                fallback_premium.append(int(row["user_id"]))
            else:
                fallback_regular.append(int(row["user_id"]))

    if fallback_premium:
        return fallback_premium[0]
    if fallback_regular:
        return fallback_regular[0]

    return None


def _has_intersection(a: set[str], b: set[str]) -> bool:
    if not a or not b:
        return False
    return not a.isdisjoint(b)


@router.message(F.text.in_({"❌ Скасувати пошук", "🚫 Скасувати пошук"}))
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
