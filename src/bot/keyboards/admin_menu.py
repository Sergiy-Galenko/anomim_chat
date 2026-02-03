from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton(text="👥 Активні користувачі", callback_data="admin:active_users")],
        [InlineKeyboardButton(text="🧾 Скарги", callback_data="admin:reports")],
        [InlineKeyboardButton(text="📥 Експорт CSV", callback_data="admin:export_stats")],
        [
            InlineKeyboardButton(text="🔒 Забанити", callback_data="admin:ban"),
            InlineKeyboardButton(text="🔓 Розбанити", callback_data="admin:unban"),
        ],
        [InlineKeyboardButton(text="🔄 Оновити", callback_data="admin:refresh")],
        [InlineKeyboardButton(text="❌ Закрити", callback_data="admin:close")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Скасувати", callback_data="admin:cancel")]]
    )


def admin_confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Підтвердити", callback_data=f"admin:confirm_{action}")],
            [InlineKeyboardButton(text="❌ Скасувати", callback_data="admin:cancel")],
        ]
    )


def report_action_keyboard(report_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚫 Бан", callback_data=f"admin:report_ban:{report_id}"
                ),
                InlineKeyboardButton(
                    text="✅ Ігнор", callback_data=f"admin:report_ignore:{report_id}"
                ),
            ],
            [InlineKeyboardButton(text="➡️ Далі", callback_data="admin:reports")],
        ]
    )
