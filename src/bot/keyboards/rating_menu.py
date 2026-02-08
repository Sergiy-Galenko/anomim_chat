from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def rating_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👍", callback_data="rate:up"),
                InlineKeyboardButton(text="👎", callback_data="rate:down"),
            ]
        ]
    )
