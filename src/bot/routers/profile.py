from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from ...config import Config
from ...db.database import Database
from ..keyboards.settings_menu import settings_keyboard
from ..keyboards.main_menu import main_menu_keyboard
from ..utils.constants import RULES_TEXT_EN, RULES_TEXT_RU, STATE_CHATTING
from ..utils.i18n import button_variants, tr, yes_no
from ..utils.admin import is_admin
from ..utils.interests import format_interest_list, parse_interests
from ..utils.premium import format_premium_until, is_premium_until
from ..utils.users import ensure_user, format_until_text, get_active_restrictions, get_state, is_banned

router = Router()


@router.message(F.text.in_(button_variants("profile")))
async def my_profile(message: Message, db: Database, config: Config) -> None:
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

    user = await db.get_user(user_id)
    state = await get_state(db, user_id)
    interests = parse_interests(user["interests"] or "")
    interest_text = format_interest_list(interests, lang)
    premium_until = user["premium_until"] or ""
    premium_active = is_premium_until(premium_until)
    premium_line = tr(lang, "⭐ Premium", "⭐ Premium") if premium_active else tr(
        lang, "Обычный", "Standard"
    )
    premium_until_text = format_premium_until(premium_until) if premium_active else "—"
    banned_until, muted_until = await get_active_restrictions(db, user_id)
    auto_search = await db.get_auto_search(user_id)
    content_filter = await db.get_content_filter(user_id)
    language_text = "Русский" if lang == "ru" else "English"

    text = tr(
        lang,
        (
            "Ваш профиль:\n"
            f"ID: {user_id}\n"
            f"Дата регистрации: {user['created_at']}\n"
            f"Чатов: {user['chats_count']}\n"
            f"Рейтинг: {user['rating']}\n"
            f"Интересы: {interest_text}\n"
            f"Статус: {premium_line}\n"
            f"Premium до: {premium_until_text}\n"
            f"Временный бан до: {format_until_text(banned_until) if banned_until else '—'}\n"
            f"Мут до: {format_until_text(muted_until) if muted_until else '—'}\n"
            f"Автопоиск: {yes_no(lang, auto_search)}\n"
            f"Фильтр контента: {yes_no(lang, content_filter)}\n"
            f"Язык: {language_text}"
        ),
        (
            "Your profile:\n"
            f"ID: {user_id}\n"
            f"Registration date: {user['created_at']}\n"
            f"Chats: {user['chats_count']}\n"
            f"Rating: {user['rating']}\n"
            f"Interests: {interest_text}\n"
            f"Status: {premium_line}\n"
            f"Premium until: {premium_until_text}\n"
            f"Temp ban until: {format_until_text(banned_until) if banned_until else '—'}\n"
            f"Mute until: {format_until_text(muted_until) if muted_until else '—'}\n"
            f"Auto-search: {yes_no(lang, auto_search)}\n"
            f"Content filter: {yes_no(lang, content_filter)}\n"
            f"Language: {language_text}"
        ),
    )
    await message.answer(
        text,
        reply_markup=main_menu_keyboard(
            show_end=state == STATE_CHATTING,
            is_admin=is_admin(user_id, config),
            lang=lang,
        ),
    )


@router.message(F.text.in_(button_variants("settings")))
async def settings(message: Message, db: Database, config: Config) -> None:
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

    auto_search = await db.get_auto_search(user_id)
    content_filter = await db.get_content_filter(user_id)
    await message.answer(
        _settings_text(lang, auto_search, content_filter),
        reply_markup=settings_keyboard(auto_search, content_filter, lang),
    )


@router.callback_query(F.data == "settings:auto_search")
async def toggle_auto_search(callback: CallbackQuery, db: Database) -> None:
    user_id = callback.from_user.id
    await ensure_user(db, user_id)

    current = await db.get_auto_search(user_id)
    await db.set_auto_search(user_id, not current)
    await _refresh_settings(callback, db, user_id)
    await callback.answer()


@router.callback_query(F.data == "settings:content_filter")
async def toggle_content_filter(callback: CallbackQuery, db: Database) -> None:
    user_id = callback.from_user.id
    await ensure_user(db, user_id)

    current = await db.get_content_filter(user_id)
    await db.set_content_filter(user_id, not current)
    await _refresh_settings(callback, db, user_id)
    await callback.answer()


@router.callback_query(F.data.startswith("settings:lang:"))
async def set_language(callback: CallbackQuery, db: Database) -> None:
    user_id = callback.from_user.id
    await ensure_user(db, user_id)

    parts = (callback.data or "").split(":")
    if len(parts) < 3:
        await callback.answer()
        return

    new_lang = parts[2]
    await db.set_lang(user_id, new_lang)
    await _refresh_settings(callback, db, user_id)
    await callback.answer()


@router.callback_query(F.data == "settings:close")
async def close_settings(callback: CallbackQuery, db: Database, config: Config) -> None:
    user_id = callback.from_user.id
    await ensure_user(db, user_id)

    lang = await db.get_lang(user_id)
    state = await get_state(db, user_id)
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            tr(lang, "Настройки сохранены.", "Settings saved."),
            reply_markup=main_menu_keyboard(
                show_end=state == STATE_CHATTING,
                is_admin=is_admin(user_id, config),
                lang=lang,
            ),
        )
    else:
        await callback.answer()
        return
    await callback.answer()


@router.message(F.text.in_(button_variants("rules")))
async def rules(message: Message, db: Database, config: Config) -> None:
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
    await message.answer(
        RULES_TEXT_EN if lang == "en" else RULES_TEXT_RU,
        reply_markup=main_menu_keyboard(
            show_end=state == STATE_CHATTING,
            is_admin=is_admin(user_id, config),
            lang=lang,
        ),
    )


async def _refresh_settings(callback: CallbackQuery, db: Database, user_id: int) -> None:
    if not callback.message:
        return
    auto_search = await db.get_auto_search(user_id)
    content_filter = await db.get_content_filter(user_id)
    lang = await db.get_lang(user_id)
    await callback.message.edit_text(
        _settings_text(lang, auto_search, content_filter),
        reply_markup=settings_keyboard(auto_search, content_filter, lang),
    )


def _settings_text(lang: str, auto_search: bool, content_filter: bool) -> str:
    return tr(
        lang,
        (
            "⚙️ Настройки\n"
            f"Автопоиск после диалога: {yes_no(lang, auto_search)}\n"
            f"Фильтр контента: {yes_no(lang, content_filter)}\n"
            f"Язык: {'Русский' if lang == 'ru' else 'English'}"
        ),
        (
            "⚙️ Settings\n"
            f"Auto-search after chat: {yes_no(lang, auto_search)}\n"
            f"Content filter: {yes_no(lang, content_filter)}\n"
            f"Language: {'Russian' if lang == 'ru' else 'English'}"
        ),
    )
