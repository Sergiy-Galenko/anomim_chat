from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from ..utils.i18n import normalize_lang

REPORT_REASON_CODES = ["spam", "abuse", "adult", "other"]
REPORT_REASON_TEXTS: dict[str, dict[str, str]] = {
    "spam": {"ru": "Спам", "en": "Spam", "uk": "Спам", "de": "Spam"},
    "abuse": {
        "ru": "Оскорбления",
        "en": "Abuse",
        "uk": "Образи",
        "de": "Beleidigung",
    },
    "adult": {"ru": "18+", "en": "18+", "uk": "18+", "de": "18+"},
    "other": {"ru": "Другое", "en": "Other", "uk": "Інше", "de": "Sonstiges"},
}

def report_keyboard(lang: str) -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(text=report_reason_label(code, lang))] for code in REPORT_REASON_CODES]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)


def report_reason_label(code: str, lang: str) -> str:
    data = REPORT_REASON_TEXTS.get(code)
    if not data:
        return code
    normalized = normalize_lang(lang)
    if normalized == "de":
        return data.get("de") or data.get("en", code)
    if normalized == "en":
        return data.get("en", code)
    if normalized == "uk":
        return data.get("uk") or data.get("ru", code)
    return data.get("ru", code)


def parse_report_reason(text: str) -> str | None:
    if not text:
        return None
    normalized = text.strip().lower()
    for code, labels in REPORT_REASON_TEXTS.items():
        label_variants = {value.lower() for value in labels.values() if value}
        if normalized in label_variants | {code.lower()}:
            return code
    if normalized in {"образи", "оскорбления", "beleidigung", "beleidigungen"}:
        return "abuse"
    if normalized in {"інше", "sonstiges"}:
        return "other"
    return None
