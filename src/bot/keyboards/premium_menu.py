from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def premium_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ 7 днів — 29 Stars", callback_data="premium:buy:7")],
            [InlineKeyboardButton(text="⭐ 30 днів — 99 Stars", callback_data="premium:buy:30")],
            [InlineKeyboardButton(text="⭐ 90 днів — 249 Stars", callback_data="premium:buy:90")],
            [InlineKeyboardButton(text="🎁 Пробний період", callback_data="premium:trial")],
            [InlineKeyboardButton(text="🏷 Промокод", callback_data="premium:promo")],
        ]
    )
