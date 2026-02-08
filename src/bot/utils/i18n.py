BUTTON_TEXTS: dict[str, dict[str, str]] = {
    "find_partner": {
        "ru": "🔍 Найти собеседника",
        "en": "🔍 Find Partner",
    },
    "find_new": {
        "ru": "🔄 Найти нового",
        "en": "🔄 Find New",
    },
    "cancel_search": {
        "ru": "🚫 Отменить поиск",
        "en": "🚫 Cancel Search",
    },
    "interests": {
        "ru": "🎯 Интересы",
        "en": "🎯 Interests",
    },
    "profile": {
        "ru": "🧑‍💻 Мой профиль",
        "en": "🧑‍💻 My Profile",
    },
    "premium": {
        "ru": "⭐ Premium",
        "en": "⭐ Premium",
    },
    "rules": {
        "ru": "❓ Правила",
        "en": "❓ Rules",
    },
    "settings": {
        "ru": "⚙️ Настройки",
        "en": "⚙️ Settings",
    },
    "report": {
        "ru": "🚨 Пожаловаться",
        "en": "🚨 Report",
    },
    "skip": {
        "ru": "⏭ Пропустить",
        "en": "⏭ Skip",
    },
    "end_dialog": {
        "ru": "🛑 Завершить диалог",
        "en": "🛑 End Chat",
    },
    "admin_partner_info": {
        "ru": "🧷 Админ: инфо партнера",
        "en": "🧷 Admin: partner info",
    },
    "admin_ban_partner": {
        "ru": "🚫 Админ: бан партнера",
        "en": "🚫 Admin: ban partner",
    },
    "admin_panel": {
        "ru": "🧰 Админ-панель",
        "en": "🧰 Admin Panel",
    },
}

LEGACY_BUTTON_TEXTS: dict[str, set[str]] = {
    "find_partner": {
        "🔍 Пошук співрозмовника",
        "🔍 Знайти співрозмовника",
        "🔍 Знайти нового",
    },
    "find_new": {"🔄 Знайти нового"},
    "cancel_search": {"❌ Скасувати пошук", "🚫 Скасувати пошук"},
    "interests": {"🎯 Інтереси"},
    "profile": {"🧑‍💻 Мій профіль"},
    "rules": {"❓ Правила"},
    "settings": {"⚙️ Налаштування"},
    "report": {"🚨 Поскаржитись"},
    "skip": {"⏭ Скіп"},
    "end_dialog": {"🛑 Завершити діалог"},
    "admin_partner_info": {"🧷 Адмін: інфо партнера"},
    "admin_ban_partner": {"🚫 Адмін: бан партнера"},
    "admin_panel": {"🧰 Адмін-панель"},
}


def normalize_lang(value: str | None) -> str:
    if not value:
        return "ru"
    lang = value.strip().lower()
    return lang if lang in {"ru", "en"} else "ru"


def tr(lang: str, ru: str, en: str) -> str:
    return en if normalize_lang(lang) == "en" else ru


def yes_no(lang: str, value: bool) -> str:
    return tr(lang, "Да" if value else "Нет", "Yes" if value else "No")


def button_text(key: str, lang: str) -> str:
    options = BUTTON_TEXTS.get(key)
    if not options:
        return key
    normalized = normalize_lang(lang)
    return options.get(normalized) or options["ru"]


def button_variants(key: str) -> set[str]:
    options = BUTTON_TEXTS.get(key, {})
    variants = {value for value in options.values() if value}
    variants.update(LEGACY_BUTTON_TEXTS.get(key, set()))
    return variants


def any_button(*keys: str) -> set[str]:
    result: set[str] = set()
    for key in keys:
        result.update(button_variants(key))
    return result
