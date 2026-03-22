from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ..utils.i18n import tr
from ..utils.virtual_companions import VIRTUAL_EXPERIMENT_VARIANTS, virtual_variant_label


def admin_menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text=tr(lang, "📊 Статистика", "📊 Statistics"), callback_data="admin:stats")],
        [
            InlineKeyboardButton(text=tr(lang, "🔎 Поиск пользователя", "🔎 Find User"), callback_data="admin:search"),
            InlineKeyboardButton(text=tr(lang, "👥 Все пользователи", "👥 All Users"), callback_data="admin:active_users"),
        ],
        [
            InlineKeyboardButton(text=tr(lang, "🎟 Промокоды", "🎟 Promo Codes"), callback_data="admin:promos"),
            InlineKeyboardButton(text=tr(lang, "🖼 Медиа файлы", "🖼 Media Files"), callback_data="admin:media"),
        ],
        [
            InlineKeyboardButton(text=tr(lang, "📣 Рассылка", "📣 Broadcast"), callback_data="admin:broadcasts"),
            InlineKeyboardButton(text=tr(lang, "🤖 Настройки ботов", "🤖 Bot Settings"), callback_data="admin:bot_settings"),
        ],
        [InlineKeyboardButton(text=tr(lang, "🧪 A/B режимы", "🧪 A/B Modes"), callback_data="admin:ab_report")],
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


def admin_user_card_keyboard(user_id: int, is_banned: bool, lang: str) -> InlineKeyboardMarkup:
    action_button = InlineKeyboardButton(
        text=tr(lang, "🔓 Разбанить", "🔓 Unban") if is_banned else tr(lang, "🔒 Забанить", "🔒 Ban"),
        callback_data=f"admin:user_unban:{user_id}" if is_banned else f"admin:user_ban:{user_id}",
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr(lang, "📜 История", "📜 History"),
                    callback_data=f"admin:user_history:{user_id}",
                )
            ],
            [action_button],
            [
                InlineKeyboardButton(
                    text=tr(lang, "↩️ В админ-панель", "↩️ Back to panel"),
                    callback_data="admin:stats",
                )
            ],
        ]
    )


def admin_promos_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr(lang, "➕ Создать промокод", "➕ Create Promo Code"),
                    callback_data="admin:promo_create",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr(lang, "🔄 Обновить", "🔄 Refresh"),
                    callback_data="admin:promos",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr(lang, "↩️ В админ-панель", "↩️ Back to panel"),
                    callback_data="admin:stats",
                )
            ],
        ]
    )


def admin_broadcasts_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr(lang, "📰 Новости", "📰 News"),
                    callback_data="admin:broadcast:news",
                ),
                InlineKeyboardButton(
                    text=tr(lang, "🔥 Промо", "🔥 Promo"),
                    callback_data="admin:broadcast:promo",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=tr(lang, "♻️ Вернуть неактивных", "♻️ Re-engage inactive"),
                    callback_data="admin:broadcast:inactive",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr(lang, "🔄 Обновить", "🔄 Refresh"),
                    callback_data="admin:broadcasts",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr(lang, "↩️ В админ-панель", "↩️ Back to panel"),
                    callback_data="admin:stats",
                )
            ],
        ]
    )


def admin_bot_settings_keyboard(
    active_ids: list[int],
    available_ids: list[int],
    active_variant_keys: list[str],
    lang: str,
) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text=tr(lang, "🔢 Кол-во в матчах", "🔢 Match count"),
                callback_data="admin:bot_count",
            ),
            InlineKeyboardButton(
                text=tr(lang, "📈 Порог людей", "📈 Human threshold"),
                callback_data="admin:bot_threshold",
            ),
        ]
    ]
    keyboard.append(
        [
            InlineKeyboardButton(
                text=tr(lang, "🧪 Метрики A/B", "🧪 A/B Metrics"),
                callback_data="admin:ab_report",
            )
        ]
    )

    variant_row = []
    active_variant_set = set(active_variant_keys)
    for variant_key in VIRTUAL_EXPERIMENT_VARIANTS:
        icon = "✅" if variant_key in active_variant_set else "⏸"
        variant_row.append(
            InlineKeyboardButton(
                text=f"{icon} {virtual_variant_label(variant_key, lang)}",
                callback_data=f"admin:ab_toggle:{variant_key}",
            )
        )
        if len(variant_row) == 2:
            keyboard.append(variant_row)
            variant_row = []
    if variant_row:
        keyboard.append(variant_row)

    row = []
    available_set = set(available_ids)
    active_set = set(active_ids)
    for companion_id in sorted(
        {*active_set, *available_set, -101, -102, -103, -104, -105},
        key=lambda value: abs(value),
    ):
        if companion_id in available_set:
            icon = "✅"
        elif companion_id in active_set:
            icon = "🟡"
        else:
            icon = "⏸"
        row.append(
            InlineKeyboardButton(
                text=f"{icon} {abs(companion_id) - 100}",
                callback_data=f"admin:bot_toggle:{companion_id}",
            )
        )
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append(
        [
            InlineKeyboardButton(
                text=tr(lang, "🔄 Обновить", "🔄 Refresh"),
                callback_data="admin:bot_settings",
            )
        ]
    )
    keyboard.append(
        [
            InlineKeyboardButton(
                text=tr(lang, "↩️ В админ-панель", "↩️ Back to panel"),
                callback_data="admin:stats",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def admin_ab_report_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr(lang, "🔄 Обновить", "🔄 Refresh"),
                    callback_data="admin:ab_report",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr(lang, "🤖 К настройкам ботов", "🤖 Back to Bot Settings"),
                    callback_data="admin:bot_settings",
                )
            ],
            [
                InlineKeyboardButton(
                    text=tr(lang, "↩️ В админ-панель", "↩️ Back to panel"),
                    callback_data="admin:stats",
                )
            ],
        ]
    )
