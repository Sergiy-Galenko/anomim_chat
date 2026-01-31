from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def searching_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Скасувати пошук")]],
        resize_keyboard=True,
    )


def find_new_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔍 Знайти нового")]],
        resize_keyboard=True,
    )
