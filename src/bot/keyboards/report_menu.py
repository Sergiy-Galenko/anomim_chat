from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

REPORT_REASON_CODES = ["spam", "abuse", "adult", "other"]
REPORT_REASON_TEXTS: dict[str, dict[str, str]] = {
    "spam": {"ru": "Спам", "en": "Spam"},
    "abuse": {"ru": "Оскорбления", "en": "Abuse"},
    "adult": {"ru": "18+", "en": "18+"},
    "other": {"ru": "Другое", "en": "Other"},
}

def report_keyboard(lang: str) -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(text=report_reason_label(code, lang))] for code in REPORT_REASON_CODES]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)


def report_reason_label(code: str, lang: str) -> str:
    data = REPORT_REASON_TEXTS.get(code)
    if not data:
        return code
    if lang == "en":
        return data.get("en", code)
    return data.get("ru", code)


def parse_report_reason(text: str) -> str | None:
    if not text:
        return None
    normalized = text.strip().lower()
    for code, labels in REPORT_REASON_TEXTS.items():
        ru_text = labels.get("ru", "").lower()
        en_text = labels.get("en", "").lower()
        if normalized in {ru_text, en_text, code.lower()}:
            return code
    if normalized in {"образи", "оскорбления"}:
        return "abuse"
    if normalized in {"інше"}:
        return "other"
    return None
