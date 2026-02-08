BLOCKED_TERMS = {
    "sex",
    "porn",
    "nude",
    "nudes",
    "xxx",
    "18+",
    "секс",
    "порно",
    "нюд",
    "эрот",
    "naked",
}


def contains_blocked_content(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(term in lowered for term in BLOCKED_TERMS)
