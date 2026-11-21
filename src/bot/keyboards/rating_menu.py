from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def rating_keyboard(pair_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👍", callback_data=f"rate:{pair_id}:up"),
                InlineKeyboardButton(text="👎", callback_data=f"rate:{pair_id}:down"),
            ]
        ]
    )
