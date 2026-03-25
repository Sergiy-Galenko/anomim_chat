from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from ...config import Config
from ...db.database import Database
from ..keyboards.interests_menu import interests_inline_keyboard
from ..keyboards.main_menu import main_menu_keyboard
from ..utils.admin import is_admin
from ..utils.chat import safe_edit_message_text
from ..utils.constants import STATE_CHATTING
from ..utils.i18n import button_variants, tr
from ..utils.interests import (
    INTEREST_CODES,
    format_interest_list,
    parse_interests,
    serialize_interests,
)
from ..utils.premium import is_premium_until
from ..utils.users import (
    ensure_user,
    get_lang_from_snapshot,
    get_state_from_snapshot,
    get_user_snapshot,
    is_banned_from_snapshot,
)

router = Router()


class InterestStates(StatesGroup):
    choosing = State()


@router.message(F.text.in_(button_variants("interests")))
async def interests_menu(message: Message, db: Database, state: FSMContext, config: Config) -> None:
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

    if get_state_from_snapshot(user) == STATE_CHATTING:
        await message.answer(
            tr(
                lang,
                "Изменить интересы можно после завершения диалога.",
                "You can change interests only after ending the chat.",
                "Змінити інтереси можна після завершення діалогу.",
                "Interessen können erst nach dem Beenden des Chats geändert werden.",
            ),
            reply_markup=main_menu_keyboard(
                show_end=True,
                is_admin=is_admin(user_id, config),
                lang=lang,
            ),
        )
        return

    selected = set(parse_interests(user["interests"] or ""))
    only_interest = bool(user["only_interest"])
    is_premium = is_premium_until(user["premium_until"] or "")

    await state.set_state(InterestStates.choosing)
    await state.update_data(
        selected=list(selected),
        only_interest=only_interest,
        is_premium=is_premium,
        lang=lang,
    )

    text = _interests_text(selected, is_premium, only_interest, lang)
    await message.answer(
        text,
        reply_markup=interests_inline_keyboard(selected, is_premium, only_interest, lang),
    )


@router.callback_query(InterestStates.choosing, F.data.startswith("interest:"))
async def interests_callback(
    callback: CallbackQuery, db: Database, state: FSMContext, config: Config
) -> None:
    user_id = callback.from_user.id
    user = await get_user_snapshot(db, user_id)
    if is_banned_from_snapshot(user):
        await state.clear()
        await callback.answer()
        return

    data = await state.get_data()
    selected = set(data.get("selected", []))
    only_interest = bool(data.get("only_interest", False))
    is_premium = bool(data.get("is_premium", False))
    lang = data.get("lang") or get_lang_from_snapshot(user)

    parts = (callback.data or "").split(":", 2)
    action = parts[1] if len(parts) > 1 else ""
    value = parts[2] if len(parts) > 2 else ""

    if action == "toggle":
        if value not in INTEREST_CODES:
            await callback.answer()
            return
        if value in selected:
            selected.remove(value)
        else:
            if not is_premium and selected:
                selected = {value}
                await callback.answer(
                    tr(
                        lang,
                        "Для нескольких интересов нужен Premium.",
                        "Premium is required for multiple interests.",
                        "Для кількох інтересів потрібен Premium.",
                        "Für mehrere Interessen ist Premium erforderlich.",
                    )
                )
            else:
                selected.add(value)
        await state.update_data(selected=list(selected))
    elif action == "only_toggle":
        if not is_premium:
            await callback.answer(
                tr(lang, "Опция доступна в Premium.", "This option is available in Premium.", "Опція доступна в Premium.", "Diese Option ist in Premium verfügbar."),
                show_alert=True,
            )
            return
        only_interest = not only_interest
        await state.update_data(only_interest=only_interest)
    elif action == "clear":
        selected.clear()
        await state.update_data(selected=list(selected))
    elif action == "none":
        await db.set_interests(user_id, "")
        await db.set_only_interest(user_id, False)
        await state.clear()
        await safe_edit_message_text(callback.message,
            tr(
                lang,
                "Интересы очищены. Поиск будет общим.",
                "Interests cleared. Search will be broad.",
                "Інтереси очищено. Пошук буде загальним.",
                "Interessen gelöscht. Die Suche wird allgemein sein.",
            ),
            reply_markup=None,
        )
        await callback.message.answer(
            tr(lang, "Возвращаюсь в меню.", "Returning to menu.", "Повертаюся в меню.", "Zurück zum Menü."),
            reply_markup=main_menu_keyboard(is_admin=is_admin(user_id, config), lang=lang),
        )
        await callback.answer()
        return
    elif action == "back":
        await state.clear()
        await safe_edit_message_text(callback.message,
            tr(lang, "Возвращаюсь в меню.", "Returning to menu.", "Повертаюся в меню.", "Zurück zum Menü."),
            reply_markup=None,
        )
        await callback.message.answer(
            tr(lang, "Выберите действие в меню.", "Choose an action from the menu.", "Оберіть дію в меню.", "Wähle eine Aktion im Menü."),
            reply_markup=main_menu_keyboard(is_admin=is_admin(user_id, config), lang=lang),
        )
        await callback.answer()
        return
    elif action == "done":
        if not selected:
            only_interest = False
        await db.set_interests(user_id, serialize_interests(sorted(selected)))
        await db.set_only_interest(user_id, bool(only_interest))
        await state.clear()
        interests_text = format_interest_list(sorted(selected), lang)
        await safe_edit_message_text(callback.message,
            tr(
                lang,
                f"Интересы сохранены: {interests_text}",
                f"Interests saved: {interests_text}",
                f"Інтереси збережено: {interests_text}",
                f"Interessen gespeichert: {interests_text}",
            ),
            reply_markup=None,
        )
        await callback.message.answer(
            tr(lang, "Возвращаюсь в меню.", "Returning to menu.", "Повертаюся в меню.", "Zurück zum Menü."),
            reply_markup=main_menu_keyboard(is_admin=is_admin(user_id, config), lang=lang),
        )
        await callback.answer()
        return

    text = _interests_text(selected, is_premium, only_interest, lang)
    await safe_edit_message_text(callback.message,
        text,
        reply_markup=interests_inline_keyboard(selected, is_premium, only_interest, lang),
    )
    await callback.answer()


def _interests_text(selected: set[str], is_premium: bool, only_interest: bool, lang: str) -> str:
    selected_text = format_interest_list(sorted(selected), lang)
    lines = [
        tr(lang, "🎯 Интересы", "🎯 Interests", "🎯 Інтереси", "🎯 Interessen"),
        tr(lang, f"Выбрано: {selected_text}", f"Selected: {selected_text}", f"Вибрано: {selected_text}", f"Ausgewählt: {selected_text}"),
    ]
    if is_premium:
        lines.append(
            tr(
                lang,
                f"Только с интересом: {'да' if only_interest else 'нет'}",
                f"Interest-only: {'on' if only_interest else 'off'}",
                f"Лише за інтересом: {'так' if only_interest else 'ні'}",
                f"Nur mit Interesse: {'an' if only_interest else 'aus'}",
            )
        )
        lines.append(
            tr(
                lang,
                "Premium: можно выбрать несколько интересов.",
                "Premium: you can choose multiple interests.",
                "Premium: можна вибрати кілька інтересів.",
                "Premium: Du kannst mehrere Interessen wählen.",
            )
        )
    else:
        lines.append(
            tr(
                lang,
                "Без Premium доступен один интерес.",
                "Without Premium, only one interest is available.",
                "Без Premium доступний лише один інтерес.",
                "Ohne Premium ist nur ein Interesse verfügbar.",
            )
        )
    return "\n".join(lines)
