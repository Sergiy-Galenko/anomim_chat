from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ..utils.i18n import tr


def premium_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr(
                        lang,
                        "⭐ 7 дней — 29 Stars",
                        "⭐ 7 days — 29 Stars",
                        "⭐ 7 днів — 29 Stars",
                        "⭐ 7 Tage — 29 Stars",
                    ),
                    callback_data="premium:buy:7",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr(
                        lang,
                        "⭐ 30 дней — 99 Stars",
                        "⭐ 30 days — 99 Stars",
                        "⭐ 30 днів — 99 Stars",
                        "⭐ 30 Tage — 99 Stars",
                    ),
                    callback_data="premium:buy:30",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr(
                        lang,
                        "⭐ 90 дней — 249 Stars",
                        "⭐ 90 days — 249 Stars",
                        "⭐ 90 днів — 249 Stars",
                        "⭐ 90 Tage — 249 Stars",
                    ),
                    callback_data="premium:buy:90",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr(lang, "🎁 Пробный период", "🎁 Trial Period", "🎁 Пробний період", "🎁 Testzeitraum"),
                    callback_data="premium:trial",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr(lang, "🏷 Промокод", "🏷 Promo Code", "🏷 Промокод", "🏷 Promo-Code"),
                    callback_data="premium:promo",
                )
            ],
        ]
    )
