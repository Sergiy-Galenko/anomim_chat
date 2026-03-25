from typing import Iterable, List

from .i18n import normalize_lang

DELIMITER = "|"

INTEREST_CODES = [
    "movies",
    "music",
    "sports",
    "games",
    "it",
    "travel",
    "books",
]

INTEREST_LABELS: dict[str, dict[str, str]] = {
    "movies": {"ru": "Кино", "en": "Movies", "uk": "Кіно", "de": "Filme"},
    "music": {"ru": "Музыка", "en": "Music", "uk": "Музика", "de": "Musik"},
    "sports": {"ru": "Спорт", "en": "Sports", "uk": "Спорт", "de": "Sport"},
    "games": {"ru": "Игры", "en": "Games", "uk": "Ігри", "de": "Spiele"},
    "it": {"ru": "IT", "en": "IT", "uk": "IT", "de": "IT"},
    "travel": {"ru": "Путешествия", "en": "Travel", "uk": "Подорожі", "de": "Reisen"},
    "books": {"ru": "Книги", "en": "Books", "uk": "Книги", "de": "Bücher"},
}

INTEREST_ALIASES: dict[str, str] = {
    # movies
    "movies": "movies",
    "movie": "movies",
    "кино": "movies",
    "кіно": "movies",
    "filme": "movies",
    "film": "movies",
    # music
    "music": "music",
    "музыка": "music",
    "музика": "music",
    "musik": "music",
    # sports
    "sports": "sports",
    "sport": "sports",
    "спорт": "sports",
    # games
    "games": "games",
    "game": "games",
    "игры": "games",
    "ігри": "games",
    "spiele": "games",
    "spiel": "games",
    # it
    "it": "it",
    # travel
    "travel": "travel",
    "travels": "travel",
    "путешествия": "travel",
    "подорожі": "travel",
    "reisen": "travel",
    "reise": "travel",
    # books
    "books": "books",
    "book": "books",
    "книги": "books",
    "bücher": "books",
    "bucher": "books",
    "buch": "books",
}


def normalize_interest(value: str) -> str | None:
    if not value:
        return None
    key = value.strip().lower()
    if not key:
        return None
    if key in INTEREST_ALIASES:
        return INTEREST_ALIASES[key]
    if key in INTEREST_CODES:
        return key
    return None


def parse_interests(raw: str) -> List[str]:
    if not raw:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in raw.split(DELIMITER):
        normalized = normalize_interest(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def serialize_interests(items: Iterable[str]) -> str:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = normalize_interest(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return DELIMITER.join(result)


def interest_label(code: str, lang: str) -> str:
    normalized = normalize_interest(code)
    if not normalized:
        return code
    labels = INTEREST_LABELS.get(normalized, {})
    normalized_lang = normalize_lang(lang)
    if normalized_lang in labels:
        return labels.get(normalized_lang, normalized)
    if normalized_lang == "de":
        return labels.get("de", labels.get("en", normalized))
    if normalized_lang == "uk":
        return labels.get("uk", labels.get("ru", normalized))
    if normalized_lang == "en":
        return labels.get("en", normalized)
    return labels.get("ru", normalized)


def format_interest_list(codes: Iterable[str], lang: str) -> str:
    labels = [interest_label(code, lang) for code in codes if code]
    return ", ".join(labels) if labels else "—"
