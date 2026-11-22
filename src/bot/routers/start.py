from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from ...config import Config
from ...db.database import Database
from ..keyboards.main_menu import main_menu_keyboard
from ..utils.constants import STATE_CHATTING, STATE_SEARCHING
from ..utils.admin import is_admin
from ..utils.i18n import button_variants, tr
from ..utils.users import (
    ensure_user,
    get_lang_from_snapshot,
    get_state_from_snapshot,
    get_user_snapshot,
    is_banned_from_snapshot,
)

router = Router()


async def _send_main_menu(message: Message, db: Database, config: Config, expanded: bool = True) -> None:
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
    if state == STATE_SEARCHING:
        text = tr(lang,
            "⏳ Поиск продолжается. Мы сообщим, когда найдём собеседника. Отменить поиск можно кнопкой ниже.",
            "⏳ Still searching. We’ll let you know when a partner is found. Cancel using the button below.",
            "⏳ Пошук триває. Повідомимо, коли знайдемо співрозмовника. Скасувати пошук можна кнопкою нижче.",
            "⏳ Die Suche läuft. Wir melden uns, sobald jemand gefunden wurde. Unten kannst du abbrechen.")
    elif state == STATE_CHATTING:
        text = tr(lang,
            "💬 Диалог продолжается. Ваши сообщения отправляются собеседнику.",
            "💬 Your chat is active. Messages you type go to your partner.",
            "💬 Розмова триває. Ваші повідомлення надсилаються співрозмовнику.",
            "💬 Dein Chat ist aktiv. Deine Nachrichten gehen an deinen Gesprächspartner.")
    else:
        text = tr(lang,
            "👋 Добро пожаловать в GhostChat!\n\nНажмите «Найти собеседника», чтобы начать общение. Интересы помогут найти общие темы.",
            "👋 Welcome to GhostChat!\n\nTap Find Partner to start chatting. Choose interests to find common topics.",
            "👋 Вітаємо в GhostChat!\n\nНатисніть «Знайти співрозмовника», щоб почати спілкування. Оберіть інтереси, щоб знайти спільні теми.",
            "👋 Willkommen bei GhostChat!\n\nTippe auf Gesprächspartner finden, um loszulegen. Wähle Interessen für gemeinsame Themen.")
    await message.answer(
        text,
        reply_markup=main_menu_keyboard(
            state=state, expanded=expanded,
            is_admin=is_admin(user_id, config), lang=lang,
        ),
    )


@router.message(CommandStart())
async def start_handler(message: Message, db: Database, config: Config, state: FSMContext) -> None:
    await state.clear()
    await _send_main_menu(message, db, config)


@router.message(Command("menu"))
@router.message(F.text.in_(button_variants("menu")))
async def menu_handler(message: Message, db: Database, config: Config, state: FSMContext) -> None:
    await state.clear()
    await _send_main_menu(message, db, config)


@router.message(F.text.in_(button_variants("back_to_chat")))
async def back_to_chat(message: Message, db: Database, config: Config, state: FSMContext) -> None:
    await state.clear()
    await _send_main_menu(message, db, config, expanded=False)
