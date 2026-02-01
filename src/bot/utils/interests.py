from typing import Iterable, List

DELIMITER = "|"


def parse_interests(raw: str) -> List[str]:
    if not raw:
        return []
    return [item for item in raw.split(DELIMITER) if item]


def serialize_interests(items: Iterable[str]) -> str:
    return DELIMITER.join([item for item in items if item])
