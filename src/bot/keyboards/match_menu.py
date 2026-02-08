from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from ..utils.i18n import button_text


def searching_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=button_text("cancel_search", lang))]],
        resize_keyboard=True,
    )


def find_new_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=button_text("find_new", lang))]],
        resize_keyboard=True,
    )
