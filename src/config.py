import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    token: str
    admin_ids: List[int]
    db_path: str


def _parse_admin_ids(raw: str) -> List[int]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return [int(p) for p in parts]


def load_config() -> Config:
    # Load environment variables from .env if present.
    load_dotenv()

    token = os.getenv("TOKEN", "").strip()
    if not token:
        raise RuntimeError("TOKEN is required in .env")

    admin_ids = _parse_admin_ids(os.getenv("ADMIN_ID", ""))
    db_path = os.getenv("DB_PATH", "ghostchat.db").strip()

    return Config(token=token, admin_ids=admin_ids, db_path=db_path)
