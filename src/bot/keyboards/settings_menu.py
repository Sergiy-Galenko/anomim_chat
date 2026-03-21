from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ..utils.i18n import tr


def settings_keyboard(auto_search: bool, lang: str) -> InlineKeyboardMarkup:
    auto_label = tr(
        lang,
        f"🔁 Автопоиск: {'ВКЛ' if auto_search else 'ВЫКЛ'}",
        f"🔁 Auto-search: {'ON' if auto_search else 'OFF'}",
    )
    ru_label = "🇷🇺 Русский ✅" if lang == "ru" else "🇷🇺 Русский"
    en_label = "🇬🇧 English ✅" if lang == "en" else "🇬🇧 English"
    close_label = tr(lang, "✅ Готово", "✅ Done")

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=auto_label, callback_data="settings:auto_search")],
            [
                InlineKeyboardButton(text=ru_label, callback_data="settings:lang:ru"),
                InlineKeyboardButton(text=en_label, callback_data="settings:lang:en"),
            ],
            [InlineKeyboardButton(text=close_label, callback_data="settings:close")],
        ]
    )
