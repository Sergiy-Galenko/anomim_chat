from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from ..utils.i18n import button_text


def main_menu_keyboard(
    show_end: bool = False,
    is_admin: bool = False,
    lang: str = "ru",
) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text=button_text("find_partner", lang))],
        [KeyboardButton(text=button_text("interests", lang))],
        [KeyboardButton(text=button_text("profile", lang))],
        [KeyboardButton(text=button_text("premium", lang))],
        [KeyboardButton(text=button_text("rules", lang))],
        [KeyboardButton(text=button_text("settings", lang))],
        [KeyboardButton(text=button_text("report", lang))],
    ]
    if show_end:
        keyboard.append([KeyboardButton(text=button_text("skip", lang))])
        keyboard.append([KeyboardButton(text=button_text("end_dialog", lang))])
        if is_admin:
            keyboard.append([KeyboardButton(text=button_text("admin_partner_info", lang))])
            keyboard.append([KeyboardButton(text=button_text("admin_ban_partner", lang))])
    if is_admin:
        keyboard.append([KeyboardButton(text=button_text("admin_panel", lang))])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
