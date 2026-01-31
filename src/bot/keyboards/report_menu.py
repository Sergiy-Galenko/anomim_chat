from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

REPORT_REASONS = ["Спам", "Образи", "18+", "Інше"]


def report_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(text=reason)] for reason in REPORT_REASONS]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)
