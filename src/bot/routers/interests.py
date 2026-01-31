from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from ...config import Config
from ...db.database import Database
from ..keyboards.interests_menu import INTEREST_OPTIONS, interests_keyboard
from ..keyboards.main_menu import main_menu_keyboard
from ..utils.admin import is_admin
from ..utils.constants import STATE_CHATTING
from ..utils.users import ensure_user, get_state, is_banned

router = Router()


class InterestStates(StatesGroup):
    waiting_choice = State()


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

    await state.set_state(InterestStates.waiting_choice)
    await message.answer("Оберіть інтерес:", reply_markup=interests_keyboard())


@router.message(InterestStates.waiting_choice)
async def interests_set(
    message: Message, db: Database, state: FSMContext, config: Config
) -> None:
    user_id = message.from_user.id
    await ensure_user(db, user_id)

    if await is_banned(db, user_id):
        await state.clear()
        return

    text = (message.text or "").strip()
    if text == "🔙 Назад":
        await state.clear()
        await message.answer(
            "Повертаюсь в меню.",
            reply_markup=main_menu_keyboard(is_admin=is_admin(user_id, config)),
        )
        return

    if text == "🚫 Без інтересу":
        await db.set_interests(user_id, "")
        await state.clear()
        await message.answer(
            "Інтерес очищено. Пошук буде загальним.",
            reply_markup=main_menu_keyboard(is_admin=is_admin(user_id, config)),
        )
        return

    if text not in INTEREST_OPTIONS:
        await message.answer("Оберіть інтерес з кнопок.")
        return

    await db.set_interests(user_id, text)
    await state.clear()
    await message.answer(
        f"Інтерес збережено: {text}",
        reply_markup=main_menu_keyboard(is_admin=is_admin(user_id, config)),
    )
