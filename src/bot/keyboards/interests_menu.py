from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

INTEREST_OPTIONS = [
    "Кіно",
    "Музика",
    "Спорт",
    "Ігри",
    "IT",
    "Подорожі",
    "Книги",
]


def interests_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(text=interest)] for interest in INTEREST_OPTIONS]
    keyboard.append([KeyboardButton(text="🚫 Без інтересу")])
    keyboard.append([KeyboardButton(text="🔙 Назад")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)
