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
from ..utils.users import (
    ensure_user,
    get_lang_from_snapshot,
    get_state_from_snapshot,
    get_user_snapshot,
    is_banned_from_snapshot,
)
from ..utils.virtual_companions import (
    available_virtual_companion_ids,
    build_virtual_intro,
    build_virtual_match_text,
    pick_virtual_companion,
    pick_virtual_variant,
)

router = Router()


@router.message(
    F.text.in_(any_button("find_partner", "find_new"))
)
async def find_partner(message: Message, db: Database, config: Config) -> None:
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
    if state == STATE_CHATTING:
        await message.answer(
            tr(
                lang,
                "У вас уже есть активный диалог. Завершите его, чтобы искать нового.",
                "You already have an active chat. End it to search for a new partner.",
                "У вас уже є активний діалог. Завершіть його, щоб шукати нового співрозмовника.",
                "Du hast bereits einen aktiven Chat. Beende ihn, um nach einem neuen Gesprächspartner zu suchen.",
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
            tr(
                lang,
                f"Вы уже в поиске.\n{status_text}",
                f"You are already searching.\n{status_text}",
                f"Ви вже в пошуку.\n{status_text}",
                f"Du suchst bereits.\n{status_text}",
            ),
            reply_markup=searching_keyboard(lang),
        )
        return

    await db.queue_user_for_search(user_id)
    status_text = await _search_status_text(db, user_id, lang)
    await message.answer(
        tr(
            lang,
            f"⏳ Ищем...\n{status_text}",
            f"⏳ Searching...\n{status_text}",
            f"⏳ Шукаємо...\n{status_text}",
            f"⏳ Suche läuft...\n{status_text}",
        ),
        reply_markup=searching_keyboard(lang),
    )

    await _attempt_match(message, db, config, user_id)


async def _attempt_match(message: Message, db: Database, config: Config, user_id: int) -> bool:
    user = await db.get_user_snapshot(user_id)
    if not user or (user["state"] or "") != STATE_SEARCHING:
        return False

    raw_interests = (user["interests"] or "").strip()
    user_interests = set(parse_interests(raw_interests))
    premium_until = user["premium_until"] or ""
    user_is_premium = is_premium_until(premium_until)
    user_only_interest = bool(user["only_interest"]) and user_is_premium
    user_wait_seconds = _seconds_since(user["joined_at"] or "")
    user_lang = get_lang_from_snapshot(user)

    candidates = await db.get_queue_candidates_limited(user_id)
    candidate_id = _pick_candidate(
        user_interests=user_interests,
        user_only=user_only_interest,
        user_wait_seconds=user_wait_seconds,
        candidates=candidates,
    )

    matched_virtual_id: int | None = None
    variant_key: str | None = None
    ab_settings: dict[str, list[str]] | None = None
    if candidate_id is None:
        bot_settings = await db.get_virtual_bot_settings()
        queue_size = await db.get_queue_size()
        if queue_size > int(bot_settings["queue_threshold"]):
            return False
        ab_settings = await db.get_virtual_ab_settings()
        allowed_virtual_ids = available_virtual_companion_ids(
            active_ids=list(bot_settings["active_ids"]),
            enabled_count=int(bot_settings["enabled_count"]),
        )
        matched_virtual_id = pick_virtual_companion(user_id, allowed_ids=allowed_virtual_ids)
        if matched_virtual_id is None:
            return False
        candidate_id = matched_virtual_id

    commit = await db.finalize_match(
        user_id,
        candidate_id,
        is_virtual=matched_virtual_id is not None,
    )
    if commit is None:
        return False

    if matched_virtual_id is not None:
        assert ab_settings is not None
        variant_key = pick_virtual_variant(
            commit.pair_id,
            user_id,
            list(ab_settings["active_variants"]),
        )
        await db.create_virtual_ab_session(
            pair_id=commit.pair_id,
            user_id=user_id,
            companion_id=matched_virtual_id,
            variant_key=variant_key,
        )
        sent_user = await safe_send_message(
            message.bot,
            user_id,
            build_virtual_match_text(user_lang),
            reply_markup=main_menu_keyboard(
                show_end=True,
                is_admin=is_admin(user_id, config),
                lang=user_lang,
            ),
        )
        if not sent_user:
            await end_chat(
                db,
                message.bot,
                user_id,
                collect_feedback=False,
                reason_ru="Собеседник недоступен. Попробуйте еще раз.",
                reason_en="Partner is unavailable. Please try again.",
                reason_uk="Співрозмовник недоступний. Спробуйте ще раз.",
                reason_de="Gesprächspartner ist nicht verfügbar. Bitte versuche es erneut.",
            )
            return False

        intro_text = build_virtual_intro(
            matched_virtual_id,
            user_id,
            user_lang,
            variant_key=variant_key,
        )
        await safe_send_message(message.bot, user_id, intro_text)
        await db.increment_virtual_ab_companion_message(commit.pair_id)
        await db.add_virtual_memory(
            pair_id=commit.pair_id,
            user_id=user_id,
            companion_id=matched_virtual_id,
            speaker="companion",
            content=intro_text,
        )
        await db.add_incident(user_id, matched_virtual_id, "virtual_match", variant_key)
        return True

    candidate = await db.get_user_snapshot(candidate_id)
    candidate_lang = get_lang_from_snapshot(candidate)
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
        await end_chat(
            db,
            message.bot,
            user_id if sent_user else candidate_id,
            collect_feedback=False,
            reason_ru="Собеседник недоступен. Попробуйте еще раз.",
            reason_en="Partner is unavailable. Please try again.",
            reason_uk="Співрозмовник недоступний. Спробуйте ще раз.",
            reason_de="Gesprächspartner ist nicht verfügbar. Bitte versuche es erneut.",
        )
        return False

    return True


def _pick_candidate(
    user_interests: set[str],
    user_only: bool,
    user_wait_seconds: int,
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
        seen_before = bool(row["seen_before"])

        if not has_overlap and (user_needs_interest or cand_needs_interest):
            continue

        score = 0
        if has_overlap:
            score += 40
        if not seen_before:
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
        if bool(row["seen_before"]):
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
    snapshot = await db.get_search_status_snapshot(user_id)
    position = int(snapshot["position"]) if snapshot else 0
    queue_size = int(snapshot["queue_size"]) if snapshot else 0
    raw_interests = (snapshot["interests"] or "").strip() if snapshot else ""
    premium_until = (snapshot["premium_until"] or "") if snapshot else ""
    is_premium = is_premium_until(premium_until)
    only_interest = bool(snapshot["only_interest"]) and is_premium if snapshot else False
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
        return tr(lang, f"~{seconds} сек", f"~{seconds} sec", f"~{seconds} с", f"~{seconds} Sek.")
    minutes = max(1, round(seconds / 60))
    return tr(lang, f"~{minutes} мин", f"~{minutes} min", f"~{minutes} хв", f"~{minutes} Min.")


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
    if state != STATE_SEARCHING:
        await message.answer(
            tr(lang, "Вы сейчас не в поиске.", "You are not currently searching.", "Ви зараз не в пошуку.", "Du suchst gerade nicht."),
            reply_markup=main_menu_keyboard(
                is_admin=is_admin(user_id, config),
                lang=lang,
            ),
        )
        return

    await db.cancel_search(user_id)
    await message.answer(
        tr(lang, "Поиск отменен.", "Search canceled.", "Пошук скасовано.", "Suche abgebrochen."),
        reply_markup=main_menu_keyboard(
            is_admin=is_admin(user_id, config),
            lang=lang,
        ),
    )
