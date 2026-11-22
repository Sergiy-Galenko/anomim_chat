from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from ..utils.constants import STATE_CHATTING, STATE_SEARCHING
from ..utils.i18n import button_text, tr
from .match_menu import searching_keyboard


def main_menu_keyboard(
    show_end: bool = False,
    is_admin: bool = False,
    lang: str = "ru",
    *,
    state: str | None = None,
    expanded: bool = False,
) -> ReplyKeyboardMarkup:
    """Keep conversation controls visible and preserve cancellation while searching."""
    if state == STATE_SEARCHING:
        return searching_keyboard(lang)
    chatting = state == STATE_CHATTING if state is not None else show_end
    if chatting and not expanded:
        rows = [["skip", "end_dialog"], ["report", "menu"]]
    else:
        rows = [
            ["back_to_chat" if chatting else "find_partner"],
            ["profile", "settings"],
            ["premium", "rules"],
        ]
        if not chatting:
            rows.insert(1, ["interests"])
    if is_admin and (expanded or not chatting):
        if chatting:
            rows.extend([["admin_partner_info"], ["admin_ban_partner"]])
        rows.append(["admin_panel"])
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=button_text(key, lang)) for key in row] for row in rows],
        resize_keyboard=True,
        input_field_placeholder=tr(
            lang,
            "Напишите собеседнику…" if chatting else "Нажмите «Найти собеседника»",
            "Message your partner…" if chatting else "Tap Find Partner to start",
            "Напишіть співрозмовнику…" if chatting else "Натисніть «Знайти співрозмовника»",
            "Schreibe deinem Gesprächspartner…" if chatting else "Tippe auf Gesprächspartner finden",
        ),
    )
