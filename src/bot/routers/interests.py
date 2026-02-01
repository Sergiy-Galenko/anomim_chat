from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from ...config import Config
from ...db.database import Database
from ..keyboards.interests_menu import INTEREST_OPTIONS, interests_inline_keyboard
from ..keyboards.main_menu import main_menu_keyboard
from ..utils.admin import is_admin
from ..utils.constants import STATE_CHATTING
from ..utils.interests import parse_interests, serialize_interests
from ..utils.premium import is_premium_until
from ..utils.users import ensure_user, get_state, is_banned

router = Router()


class InterestStates(StatesGroup):
    choosing = State()


@router.message(F.text == "🎯 Інтереси")
async def interests_menu(message: Message, db: Database, state: FSMContext, config: Config) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)

    if await is_banned(db, user_id):
        return

    if await get_state(db, user_id) == STATE_CHATTING:
        await message.answer(
            "Змінити інтереси можна після завершення діалогу.",
            reply_markup=main_menu_keyboard(show_end=True, is_admin=is_admin(user_id, config)),
        )
        return

    raw_interests = await db.get_interests(user_id)
    selected = set(parse_interests(raw_interests))
    only_interest = await db.get_only_interest(user_id)
    premium_until = await db.get_premium_until(user_id)
    is_premium = is_premium_until(premium_until)

    await state.set_state(InterestStates.choosing)
    await state.update_data(selected=list(selected), only_interest=only_interest, is_premium=is_premium)

    text = _interests_text(selected, is_premium, only_interest)
    await message.answer(
        text,
        reply_markup=interests_inline_keyboard(selected, is_premium, only_interest),
    )


@router.callback_query(InterestStates.choosing, F.data.startswith("interest:"))
async def interests_callback(
    callback: CallbackQuery, db: Database, state: FSMContext, config: Config
) -> None:
    user_id = callback.from_user.id
    if await is_banned(db, user_id):
        await state.clear()
        await callback.answer()
        return

    data = await state.get_data()
    selected = set(data.get("selected", []))
    only_interest = bool(data.get("only_interest", False))
    is_premium = bool(data.get("is_premium", False))

    parts = (callback.data or "").split(":", 2)
    action = parts[1] if len(parts) > 1 else ""
    value = parts[2] if len(parts) > 2 else ""

    if action == "toggle":
        if value not in INTEREST_OPTIONS:
            await callback.answer()
            return
        if value in selected:
            selected.remove(value)
        else:
            if not is_premium and selected:
                selected = {value}
                await callback.answer("Для кількох інтересів потрібен Premium.")
            else:
                selected.add(value)
        await state.update_data(selected=list(selected))
    elif action == "only_toggle":
        if not is_premium:
            await callback.answer("Опція доступна в Premium.", show_alert=True)
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
        await callback.message.edit_text(
            "Інтерес очищено. Пошук буде загальним.",
            reply_markup=None,
        )
        await callback.message.answer(
            "Повертаюсь в меню.",
            reply_markup=main_menu_keyboard(is_admin=is_admin(user_id, config)),
        )
        await callback.answer()
        return
    elif action == "back":
        await state.clear()
        await callback.message.edit_text("Повертаюсь в меню.", reply_markup=None)
        await callback.message.answer(
            "Оберіть дію з меню.",
            reply_markup=main_menu_keyboard(is_admin=is_admin(user_id, config)),
        )
        await callback.answer()
        return
    elif action == "done":
        if not selected:
            only_interest = False
        await db.set_interests(user_id, serialize_interests(sorted(selected)))
        await db.set_only_interest(user_id, bool(only_interest))
        await state.clear()
        interests_text = ", ".join(sorted(selected)) if selected else "—"
        await callback.message.edit_text(
            f"Інтереси збережено: {interests_text}",
            reply_markup=None,
        )
        await callback.message.answer(
            "Повертаюсь в меню.",
            reply_markup=main_menu_keyboard(is_admin=is_admin(user_id, config)),
        )
        await callback.answer()
        return

    text = _interests_text(selected, is_premium, only_interest)
    await callback.message.edit_text(
        text,
        reply_markup=interests_inline_keyboard(selected, is_premium, only_interest),
    )
    await callback.answer()


def _interests_text(selected: set[str], is_premium: bool, only_interest: bool) -> str:
    selected_text = ", ".join(sorted(selected)) if selected else "—"
    lines = [
        "🎯 Інтереси",
        f"Обрано: {selected_text}",
    ]
    if is_premium:
        lines.append(f"Тільки з інтересом: {'так' if only_interest else 'ні'}")
        lines.append("Premium: можна обрати кілька інтересів.")
    else:
        lines.append("Без Premium доступний один інтерес.")
    return "\n".join(lines)
