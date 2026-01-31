from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton(text="👥 Активні користувачі", callback_data="admin:active_users")],
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
