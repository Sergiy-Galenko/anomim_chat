import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    token: str
    admin_ids: List[int]
    db_path: str
    promo_codes: Dict[str, int]
    trial_days: int
    telegram_proxy: Optional[str]
    telegram_timeout_sec: float
    telegram_webhook_secret: Optional[str]


def _parse_admin_ids(raw: str) -> List[int]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return [int(p) for p in parts]


def _parse_promo_codes(raw: str) -> Dict[str, int]:
    if not raw:
        return {}
    result: Dict[str, int] = {}
    for part in raw.split(","):
        item = part.strip()
        if not item or ":" not in item:
            continue
        code, days = item.split(":", 1)
        code = code.strip().upper()
        try:
            days_int = int(days.strip())
        except ValueError:
            continue
        if days_int > 0:
            result[code] = days_int
    return result


def _parse_positive_float(raw: str, default: float) -> float:
    if not raw:
        return default
    try:
        value = float(raw.strip())
    except ValueError:
        return default
    return value if value > 0 else default


def _resolve_telegram_proxy() -> Optional[str]:
    for key in (
        "TELEGRAM_PROXY",
        "ALL_PROXY",
        "all_proxy",
        "HTTPS_PROXY",
        "https_proxy",
        "HTTP_PROXY",
        "http_proxy",
    ):
        value = os.getenv(key, "").strip()
        if value:
            return value
    return None


def _resolve_db_path() -> str:
    raw = os.getenv("DB_PATH", "").strip()
    if raw:
        return raw
    if os.getenv("VERCEL"):
        return "/tmp/ghostchat.db"
    return "ghostchat.db"


def load_config() -> Config:
    # Load environment variables from .env if present.
    load_dotenv()

    token = os.getenv("TOKEN", "").strip()
    if not token:
        raise RuntimeError("TOKEN environment variable is required")

    admin_ids = _parse_admin_ids(os.getenv("ADMIN_ID", ""))
    db_path = _resolve_db_path()
    promo_codes = _parse_promo_codes(os.getenv("PROMO_CODES", ""))
    trial_days = int(os.getenv("TRIAL_DAYS", "3").strip() or "3")
    telegram_proxy = _resolve_telegram_proxy()
    telegram_timeout_sec = _parse_positive_float(
        os.getenv("TELEGRAM_TIMEOUT_SEC", ""),
        default=60.0,
    )
    telegram_webhook_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip() or None

    return Config(
        token=token,
        admin_ids=admin_ids,
        db_path=db_path,
        promo_codes=promo_codes,
        trial_days=trial_days,
        telegram_proxy=telegram_proxy,
        telegram_timeout_sec=telegram_timeout_sec,
        telegram_webhook_secret=telegram_webhook_secret,
    )
