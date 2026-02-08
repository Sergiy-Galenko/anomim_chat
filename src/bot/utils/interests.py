from typing import Iterable, List

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
    "movies": {"ru": "Кино", "en": "Movies"},
    "music": {"ru": "Музыка", "en": "Music"},
    "sports": {"ru": "Спорт", "en": "Sports"},
    "games": {"ru": "Игры", "en": "Games"},
    "it": {"ru": "IT", "en": "IT"},
    "travel": {"ru": "Путешествия", "en": "Travel"},
    "books": {"ru": "Книги", "en": "Books"},
}

INTEREST_ALIASES: dict[str, str] = {
    # movies
    "movies": "movies",
    "movie": "movies",
    "кино": "movies",
    "кіно": "movies",
    # music
    "music": "music",
    "музыка": "music",
    "музика": "music",
    # sports
    "sports": "sports",
    "sport": "sports",
    "спорт": "sports",
    # games
    "games": "games",
    "game": "games",
    "игры": "games",
    "ігри": "games",
    # it
    "it": "it",
    # travel
    "travel": "travel",
    "travels": "travel",
    "путешествия": "travel",
    "подорожі": "travel",
    # books
    "books": "books",
    "book": "books",
    "книги": "books",
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
    if lang == "en":
        return labels.get("en", normalized)
    return labels.get("ru", normalized)


def format_interest_list(codes: Iterable[str], lang: str) -> str:
    labels = [interest_label(code, lang) for code in codes if code]
    return ", ".join(labels) if labels else "—"
