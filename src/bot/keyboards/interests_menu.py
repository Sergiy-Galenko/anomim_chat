from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

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


def interests_inline_keyboard(
    selected: set[str], is_premium: bool, only_interest: bool
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for interest in INTEREST_OPTIONS:
        prefix = "✅ " if interest in selected else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{prefix}{interest}", callback_data=f"interest:toggle:{interest}"
                )
            ]
        )

    if is_premium:
        toggle_text = "🔒 Тільки з інтересом: ТАК" if only_interest else "🔓 Тільки з інтересом: НІ"
        rows.append([InlineKeyboardButton(text=toggle_text, callback_data="interest:only_toggle")])

    rows.append(
        [
            InlineKeyboardButton(text="✅ Готово", callback_data="interest:done"),
            InlineKeyboardButton(text="🧹 Очистити", callback_data="interest:clear"),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(text="🚫 Без інтересу", callback_data="interest:none"),
            InlineKeyboardButton(text="🔙 Назад", callback_data="interest:back"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
