from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.types import Message

from ...config import Config
from ...db.database import Database
from ..keyboards.main_menu import main_menu_keyboard
from ..keyboards.match_menu import searching_keyboard
from ..utils.chat import end_chat, safe_send_message
from ..utils.constants import (
    MATCH_SOFT_EXPAND_SECONDS,
    STATE_CHATTING,
    STATE_IDLE,
    STATE_SEARCHING,
)
from ..utils.admin import is_admin
from ..utils.i18n import any_button, tr
from ..utils.interests import parse_interests
from ..utils.premium import is_premium_until
from ..utils.users import ensure_user, get_state, is_banned

router = Router()


@router.message(
    F.text.in_(any_button("find_partner", "find_new"))
)
async def find_partner(message: Message, db: Database, config: Config) -> None:
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
    if state == STATE_CHATTING:
        await message.answer(
            tr(
                lang,
                "У вас уже есть активный диалог. Завершите его, чтобы искать нового.",
                "You already have an active chat. End it to search for a new partner.",
            ),
            reply_markup=main_menu_keyboard(
                show_end=True,
                is_admin=is_admin(user_id, config),
                lang=lang,
            ),
        )
        return

    if state == STATE_SEARCHING:
        status_text = await _search_status_text(db, user_id, lang)
        await message.answer(
            tr(lang, f"Вы уже в поиске.\n{status_text}", f"You are already searching.\n{status_text}"),
            reply_markup=searching_keyboard(lang),
        )
        return

    await db.set_state(user_id, STATE_SEARCHING)
    await db.add_to_queue(user_id)
    status_text = await _search_status_text(db, user_id, lang)
    await message.answer(
        tr(lang, f"⏳ Ищем...\n{status_text}", f"⏳ Searching...\n{status_text}"),
        reply_markup=searching_keyboard(lang),
    )

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
        user_wait_seconds = _seconds_since(await db.get_queue_joined_at(user_id))
        partner_history = await db.get_partner_history(user_id)

        candidates = await db.get_queue_candidates(user_id)
        candidate_id = _pick_candidate(
            user_interests=user_interests,
            user_only=user_only_interest,
            user_wait_seconds=user_wait_seconds,
            partner_history=partner_history,
            candidates=candidates,
        )
        if not candidate_id:
            return False

        await db.remove_from_queue(user_id)
        await db.remove_from_queue(candidate_id)
        await db.set_state(user_id, STATE_CHATTING)
        await db.set_state(candidate_id, STATE_CHATTING)
        await db.create_pair(user_id, candidate_id)
        await db.increment_chats(user_id)
        await db.increment_chats(candidate_id)

    user_lang = await db.get_lang(user_id)
    candidate_lang = await db.get_lang(candidate_id)
    sent_user = await safe_send_message(
        message.bot,
        user_id,
        tr(
            user_lang,
            "✅ Собеседник найден. Пишите сообщение.",
            "✅ Partner found. Start chatting.",
        ),
        reply_markup=main_menu_keyboard(
            show_end=True,
            is_admin=is_admin(user_id, config),
            lang=user_lang,
        ),
    )
    sent_candidate = await safe_send_message(
        message.bot,
        candidate_id,
        tr(
            candidate_lang,
            "✅ Собеседник найден. Пишите сообщение.",
            "✅ Partner found. Start chatting.",
        ),
        reply_markup=main_menu_keyboard(
            show_end=True,
            is_admin=is_admin(candidate_id, config),
            lang=candidate_lang,
        ),
    )

    if not sent_user or not sent_candidate:
        # If one user is unavailable, end the chat for the other.
        await end_chat(
            db,
            message.bot,
            user_id if sent_user else candidate_id,
            collect_feedback=False,
            reason_ru="Собеседник недоступен. Попробуйте еще раз.",
            reason_en="Partner is unavailable. Please try again.",
        )
        return False

    return True


def _pick_candidate(
    user_interests: set[str],
    user_only: bool,
    user_wait_seconds: int,
    partner_history: set[int],
    candidates,
) -> int | None:
    if user_only and not user_interests:
        return None

    user_needs_interest = user_only or (
        bool(user_interests) and user_wait_seconds < MATCH_SOFT_EXPAND_SECONDS
    )

    best_candidate_id: int | None = None
    best_score: int | None = None

    for row in candidates:
        candidate_id = int(row["user_id"])
        cand_interests = set(parse_interests(row["interests"] or ""))
        cand_premium = is_premium_until(row["premium_until"] or "")
        cand_only = bool(row["only_interest"]) and cand_premium
        cand_wait_seconds = _seconds_since(row["joined_at"] or "")
        cand_needs_interest = cand_only or (
            bool(cand_interests) and cand_wait_seconds < MATCH_SOFT_EXPAND_SECONDS
        )
        has_overlap = _has_intersection(user_interests, cand_interests)

        if not has_overlap and (user_needs_interest or cand_needs_interest):
            continue

        score = 0
        if has_overlap:
            score += 40
        if candidate_id not in partner_history:
            score += 80
        if cand_premium:
            score += 5
        score += min(cand_wait_seconds, 180) // 15

        if best_score is None or score > best_score:
            best_score = score
            best_candidate_id = candidate_id

    if best_candidate_id is not None:
        return best_candidate_id

    if user_needs_interest:
        return None

    fallback_fresh: list[int] = []
    fallback_repeat: list[int] = []
    for row in candidates:
        candidate_id = int(row["user_id"])
        cand_premium = is_premium_until(row["premium_until"] or "")
        cand_only = bool(row["only_interest"]) and cand_premium
        if cand_only:
            continue
        if candidate_id in partner_history:
            fallback_repeat.append(candidate_id)
        else:
            fallback_fresh.append(candidate_id)

    if fallback_fresh:
        return fallback_fresh[0]
    if fallback_repeat:
        return fallback_repeat[0]

    return None


def _has_intersection(a: set[str], b: set[str]) -> bool:
    if not a or not b:
        return False
    return not a.isdisjoint(b)


async def _search_status_text(db: Database, user_id: int, lang: str) -> str:
    position = await db.get_queue_position(user_id)
    queue_size = await db.get_queue_size()
    raw_interests = (await db.get_interests(user_id)).strip()
    premium_until = await db.get_premium_until(user_id)
    is_premium = is_premium_until(premium_until)
    only_interest = await db.get_only_interest(user_id) and is_premium
    eta_seconds = _estimate_wait_seconds(position, bool(raw_interests), only_interest)

    if position <= 0:
        return tr(
            lang,
            "Обновите поиск, если долго нет пары.",
            "Refresh search if no partner is found for a long time.",
        )

    return tr(
        lang,
        (
            f"Позиция в очереди: {position}/{max(queue_size, position)}\n"
            f"Ориентировочное ожидание: {_format_eta(eta_seconds, lang)}"
        ),
        (
            f"Queue position: {position}/{max(queue_size, position)}\n"
            f"Estimated wait: {_format_eta(eta_seconds, lang)}"
        ),
    )


def _estimate_wait_seconds(position: int, has_interest: bool, only_interest: bool) -> int:
    if position <= 1:
        base = 15
    else:
        base = 15 + (position - 1) * 18
    if has_interest:
        base += 12
    if only_interest:
        base += 24
    return min(base, 6 * 60)


def _format_eta(seconds: int, lang: str) -> str:
    if seconds < 60:
        return tr(lang, f"~{seconds} сек", f"~{seconds} sec")
    minutes = max(1, round(seconds / 60))
    return tr(lang, f"~{minutes} мин", f"~{minutes} min")


def _seconds_since(raw_iso: str) -> int:
    if not raw_iso:
        return 0
    try:
        dt = datetime.fromisoformat(raw_iso)
    except ValueError:
        return 0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if dt >= now:
        return 0
    return int((now - dt).total_seconds())


@router.message(F.text.in_(any_button("cancel_search")))
async def cancel_search(message: Message, db: Database, config: Config) -> None:
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
    if state != STATE_SEARCHING:
        await message.answer(
            tr(lang, "Вы сейчас не в поиске.", "You are not currently searching."),
            reply_markup=main_menu_keyboard(
                is_admin=is_admin(user_id, config),
                lang=lang,
            ),
        )
        return

    await db.remove_from_queue(user_id)
    await db.set_state(user_id, STATE_IDLE)
    await message.answer(
        tr(lang, "Поиск отменен.", "Search canceled."),
        reply_markup=main_menu_keyboard(
            is_admin=is_admin(user_id, config),
            lang=lang,
        ),
    )
