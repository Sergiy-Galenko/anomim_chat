from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ..utils.i18n import tr


def admin_menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text=tr(lang, "📊 Статистика", "📊 Statistics"), callback_data="admin:stats")],
        [InlineKeyboardButton(text=tr(lang, "👥 Все пользователи", "👥 All Users"), callback_data="admin:active_users")],
        [InlineKeyboardButton(text=tr(lang, "🖼 Медиа файлы", "🖼 Media Files"), callback_data="admin:media")],
        [InlineKeyboardButton(text=tr(lang, "🧾 Жалобы", "🧾 Reports"), callback_data="admin:reports")],
        [InlineKeyboardButton(text=tr(lang, "📥 Экспорт CSV", "📥 Export CSV"), callback_data="admin:export_stats")],
        [
            InlineKeyboardButton(text=tr(lang, "🔒 Забанить", "🔒 Ban"), callback_data="admin:ban"),
            InlineKeyboardButton(text=tr(lang, "🔓 Разбанить", "🔓 Unban"), callback_data="admin:unban"),
        ],
        [InlineKeyboardButton(text=tr(lang, "🔄 Обновить", "🔄 Refresh"), callback_data="admin:refresh")],
        [InlineKeyboardButton(text=tr(lang, "❌ Закрыть", "❌ Close"), callback_data="admin:close")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_cancel_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=tr(lang, "❌ Отмена", "❌ Cancel"), callback_data="admin:cancel")]
        ]
    )


def admin_confirm_keyboard(action: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=tr(lang, "✅ Подтвердить", "✅ Confirm"), callback_data=f"admin:confirm_{action}")],
            [InlineKeyboardButton(text=tr(lang, "❌ Отмена", "❌ Cancel"), callback_data="admin:cancel")],
        ]
    )


def report_action_keyboard(report_id: int, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr(lang, "🚫 Бан", "🚫 Ban"), callback_data=f"admin:report_ban:{report_id}"
                ),
                InlineKeyboardButton(
                    text=tr(lang, "✅ Игнор", "✅ Ignore"), callback_data=f"admin:report_ignore:{report_id}"
                ),
            ],
            [InlineKeyboardButton(text=tr(lang, "➡️ Далее", "➡️ Next"), callback_data="admin:reports")],
        ]
    )


def admin_media_keyboard(page: int, has_prev: bool, has_next: bool, lang: str) -> InlineKeyboardMarkup:
    keyboard = []
    nav_row = []
    if has_prev:
        nav_row.append(
            InlineKeyboardButton(
                text=tr(lang, "⬅️ Назад", "⬅️ Back"),
                callback_data=f"admin:media:{page - 1}",
            )
        )
    if has_next:
        nav_row.append(
            InlineKeyboardButton(
                text=tr(lang, "➡️ Далее", "➡️ Next"),
                callback_data=f"admin:media:{page + 1}",
            )
        )
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append(
        [InlineKeyboardButton(text=tr(lang, "🔄 Обновить", "🔄 Refresh"), callback_data=f"admin:media:{page}")]
    )
    keyboard.append(
        [InlineKeyboardButton(text=tr(lang, "↩️ В админ-панель", "↩️ Back to panel"), callback_data="admin:stats")]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_media_item_keyboard(media_id: int, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr(lang, "🗑 Удалить", "🗑 Delete"),
                    callback_data=f"admin:media_delete:{media_id}",
                )
            ]
        ]
    )
