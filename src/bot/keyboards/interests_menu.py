from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from ..utils.interests import INTEREST_CODES, interest_label
from ..utils.i18n import tr


def interests_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(text=interest_label(interest, lang))] for interest in INTEREST_CODES]
    keyboard.append([KeyboardButton(text=tr(lang, "🚫 Без интересов", "🚫 No Interests"))])
    keyboard.append([KeyboardButton(text=tr(lang, "🔙 Назад", "🔙 Back"))])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)


def interests_inline_keyboard(
    selected: set[str], is_premium: bool, only_interest: bool, lang: str
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for interest in INTEREST_CODES:
        prefix = "✅ " if interest in selected else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{prefix}{interest_label(interest, lang)}",
                    callback_data=f"interest:toggle:{interest}",
                )
            ]
        )

    if is_premium:
        toggle_text = tr(
            lang,
            f"{'🔒' if only_interest else '🔓'} Только с интересом: {'ДА' if only_interest else 'НЕТ'}",
            f"{'🔒' if only_interest else '🔓'} Interest-only: {'ON' if only_interest else 'OFF'}",
        )
        rows.append([InlineKeyboardButton(text=toggle_text, callback_data="interest:only_toggle")])

    rows.append(
        [
            InlineKeyboardButton(text=tr(lang, "✅ Готово", "✅ Done"), callback_data="interest:done"),
            InlineKeyboardButton(text=tr(lang, "🧹 Очистить", "🧹 Clear"), callback_data="interest:clear"),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(text=tr(lang, "🚫 Без интересов", "🚫 No Interests"), callback_data="interest:none"),
            InlineKeyboardButton(text=tr(lang, "🔙 Назад", "🔙 Back"), callback_data="interest:back"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
