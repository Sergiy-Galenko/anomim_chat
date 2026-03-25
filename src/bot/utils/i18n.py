BUTTON_TEXTS: dict[str, dict[str, str]] = {
    "find_partner": {
        "ru": "🔍 Найти собеседника",
        "en": "🔍 Find Partner",
        "uk": "🔍 Знайти співрозмовника",
        "de": "🔍 Gesprächspartner finden",
    },
    "find_new": {
        "ru": "🔄 Найти нового",
        "en": "🔄 Find New",
        "uk": "🔄 Знайти нового",
        "de": "🔄 Neu suchen",
    },
    "menu": {
        "ru": "🏠 Меню",
        "en": "🏠 Menu",
        "uk": "🏠 Меню",
        "de": "🏠 Menü",
    },
    "cancel_search": {
        "ru": "🚫 Отменить поиск",
        "en": "🚫 Cancel Search",
        "uk": "🚫 Скасувати пошук",
        "de": "🚫 Suche abbrechen",
    },
    "interests": {
        "ru": "🎯 Интересы",
        "en": "🎯 Interests",
        "uk": "🎯 Інтереси",
        "de": "🎯 Interessen",
    },
    "profile": {
        "ru": "🧑‍💻 Мой профиль",
        "en": "🧑‍💻 My Profile",
        "uk": "🧑‍💻 Мій профіль",
        "de": "🧑‍💻 Mein Profil",
    },
    "premium": {
        "ru": "⭐ Premium",
        "en": "⭐ Premium",
        "uk": "⭐ Premium",
        "de": "⭐ Premium",
    },
    "rules": {
        "ru": "❓ Правила",
        "en": "❓ Rules",
        "uk": "❓ Правила",
        "de": "❓ Regeln",
    },
    "settings": {
        "ru": "⚙️ Настройки",
        "en": "⚙️ Settings",
        "uk": "⚙️ Налаштування",
        "de": "⚙️ Einstellungen",
    },
    "report": {
        "ru": "🚨 Пожаловаться",
        "en": "🚨 Report",
        "uk": "🚨 Поскаржитися",
        "de": "🚨 Melden",
    },
    "skip": {
        "ru": "⏭ Пропустить",
        "en": "⏭ Skip",
        "uk": "⏭ Пропустити",
        "de": "⏭ Überspringen",
    },
    "end_dialog": {
        "ru": "🛑 Завершить диалог",
        "en": "🛑 End Chat",
        "uk": "🛑 Завершити діалог",
        "de": "🛑 Chat beenden",
    },
    "admin_partner_info": {
        "ru": "🧷 Админ: инфо партнера",
        "en": "🧷 Admin: partner info",
        "uk": "🧷 Адмін: інфо партнера",
        "de": "🧷 Admin: Partnerinfo",
    },
    "admin_ban_partner": {
        "ru": "🚫 Админ: бан партнера",
        "en": "🚫 Admin: ban partner",
        "uk": "🚫 Адмін: бан партнера",
        "de": "🚫 Admin: Partner sperren",
    },
    "admin_panel": {
        "ru": "🧰 Админ-панель",
        "en": "🧰 Admin Panel",
        "uk": "🧰 Адмін-панель",
        "de": "🧰 Admin-Bereich",
    },
}

LEGACY_BUTTON_TEXTS: dict[str, set[str]] = {
    "find_partner": {
        "🔍 Пошук співрозмовника",
        "🔍 Знайти співрозмовника",
        "🔍 Знайти нового",
    },
    "find_new": {"🔄 Знайти нового"},
    "menu": {"🏠 Меню"},
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
    return lang if lang in {"ru", "en", "uk", "de"} else "ru"

def tr(lang: str, ru: str, en: str, uk: str | None = None, de: str | None = None) -> str:
    normalized = normalize_lang(lang)
    if normalized == "en":
        return en
    if normalized == "uk":
        return uk if uk is not None else ru
    if normalized == "de":
        return de if de is not None else en
    return ru


def yes_no(lang: str, value: bool) -> str:
    return tr(
        lang,
        "Да" if value else "Нет",
        "Yes" if value else "No",
        "Так" if value else "Ні",
        "Ja" if value else "Nein",
    )


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
