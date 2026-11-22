"""Poll public competitor pages; no bot login, chats, or Telegram credentials required."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sqlite3
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser

USER_AGENT = "GhostChatResearchBot/1.0"
MAX_BYTES = 2_000_000
DEFAULT_SOURCES = Path(__file__).resolve().parents[1] / "config/competitor_sources.json"
LOG = logging.getLogger(__name__)
# These are mentions in public copy, not verified capabilities.
FEATURE_PATTERNS = {
    "interests": r"\binterests?\b|інтерес|интерес",
    "voice": r"\bvoice\b|голосов",
    "video": r"\bvideo\b|відео|видео",
    "photos": r"\bphotos?\b|фото",
    "report": r"\breport\b|скарг|жалоб",
    "block": r"\bblock\b|блокув|блокир",
    "premium": r"\bpremium\b|\bvip\b",
    "language_filter": r"language filters?|мовн\w* фільтр|языков\w* фильтр",
    "gender_filter": r"gender (?:filter|search)|фільтр за статтю|фильтр по полу",
    "next": r"/next\b|press next|tap next",
    "stop": r"/stop\b|stop to leave",
}


class PublicPageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.in_title = False
        self.title_parts = []
        self.parts = []
        self.meta = {}
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style", "noscript", "template"}:
            self.hidden += 1
        if self.hidden:
            return
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or "").lower()
            self.meta[key] = attrs.get("content") or ""
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "template"}:
            self.hidden = max(0, self.hidden - 1)
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)
            if self.in_title:
                self.title_parts.append(data)


def clean(text: str, limit: int) -> str:
    return " ".join(text.split())[:limit]


def extract(html: str, url: str) -> dict:
    page = PublicPageParser()
    page.feed(html)
    title = clean(page.meta.get("og:title") or " ".join(page.title_parts), 200)
    description = clean(page.meta.get("description") or page.meta.get("og:description", ""), 240)
    visible = " ".join(page.parts)
    searchable = " ".join((visible, title, description))
    bots = set()
    for link in [url, *page.links]:
        parsed = urlsplit(urljoin(url, link))
        if parsed.scheme == "https" and parsed.hostname in {"t.me", "telegram.me"}:
            handle = parsed.path.strip("/")
            if re.fullmatch(r"[a-zA-Z0-9_]{5,32}", handle) and handle.lower().endswith("bot"):
                bots.add("https://t.me/" + handle.lower())
    return {
        "title": title,
        "description": description,
        "bot_links": sorted(bots),
        "mentioned_features": sorted(key for key, pattern in FEATURE_PATTERNS.items()
                                     if re.search(pattern, searchable, re.IGNORECASE)),
        "commands": sorted(set(re.findall(r"(?<![\w:/])/(?:search|next|stop|settings|report|block)\b", visible))),
    }


def validate_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Sources must be public HTTPS URLs without credentials or custom ports")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))


def load_sources(path: Path) -> list[dict]:
    sources = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(sources, list) or not 1 <= len(sources) <= 50:
        raise ValueError("Configure between 1 and 50 sources")
    seen = set()
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("name"), str) or not source["name"].strip():
            raise ValueError("Every source needs a non-empty name")
        source["url"] = validate_url(source["url"])
        if source["url"] in seen:
            raise ValueError("Duplicate source URL: " + source["url"])
        seen.add(source["url"])
    return sources


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class PublicFetcher:
    def __init__(self, timeout: float = 20):
        self.opener = build_opener(NoRedirect())
        self.timeout = timeout
        self.robots = {}
        self.last_request = {}

    def request(self, url: str, delay: float = 2) -> tuple[int, dict, str]:
        validate_url(url)
        host = urlsplit(url).netloc
        wait = self.last_request.get(host, 0) + delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain;q=0.9"})
        try:
            response = self.opener.open(request, timeout=self.timeout)
        except HTTPError as exc:
            response = exc
        try:
            with response:
                body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise ValueError("Response exceeds 2 MB limit")
                charset = response.headers.get_content_charset() or "utf-8"
                return response.status, dict(response.headers.items()), body.decode(charset, errors="replace")
        finally:
            self.last_request[host] = time.monotonic()

    def policy(self, url: str) -> RobotFileParser:
        parsed = urlsplit(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self.robots:
            status, _, body = self.request(origin + "/robots.txt")
            policy = RobotFileParser()
            if status == 200:
                policy.parse(body.splitlines())
            elif status in {404, 410}:
                policy.parse([])
            else:
                raise ValueError(f"robots.txt unavailable (HTTP {status}); skipped")
            self.robots[origin] = policy
        return self.robots[origin]

    def fetch(self, url: str) -> tuple[str, str]:
        for _ in range(4):
            policy = self.policy(url)
            if not policy.can_fetch(USER_AGENT, url):
                raise ValueError("robots.txt disallows this page")
            delay = max(2, policy.crawl_delay(USER_AGENT) or 0)
            rate = policy.request_rate(USER_AGENT)
            if rate and rate.requests:
                delay = max(delay, rate.seconds / rate.requests)
            status, headers, body = self.request(url, delay)
            headers = {key.lower(): value for key, value in headers.items()}
            if status in {301, 302, 303, 307, 308}:
                target = validate_url(urljoin(url, headers.get("location", "")))
                if urlsplit(target).hostname != urlsplit(url).hostname:
                    raise ValueError("Cross-host redirect: configure the canonical source URL")
                url = target
                continue
            if status != 200:
                raise ValueError(f"HTTP {status}")
            if "text/html" not in headers.get("content-type", "").lower():
                raise ValueError("Source is not an HTML page")
            return url, body
        raise ValueError("Too many redirects")


def open_store(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS observations (
        id INTEGER PRIMARY KEY, source_url TEXT NOT NULL, source_name TEXT NOT NULL,
        checked_at TEXT NOT NULL, status TEXT NOT NULL, final_url TEXT,
        fingerprint TEXT, data_json TEXT, error TEXT, changed INTEGER NOT NULL DEFAULT 0
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS observations_source ON observations(source_url, id)")
    db.commit()
    return db


def run_once(sources: list[dict], db: sqlite3.Connection, fetcher: PublicFetcher, keep: int = 120) -> dict:
    results = []
    for source in sources:
        url, name = source["url"], source["name"]
        checked = datetime.now(timezone.utc).isoformat()
        final_url = fingerprint = payload = error = None
        changed = False
        try:
            final_url, html = fetcher.fetch(url)
            data = extract(html, final_url)
            if not data["title"]:
                raise ValueError("No page title found; page may require JavaScript")
            payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
            fingerprint = hashlib.sha256(payload.encode()).hexdigest()
            previous = db.execute(
                "SELECT fingerprint FROM observations WHERE source_url=? AND status='ok' ORDER BY id DESC LIMIT 1", (url,)
            ).fetchone()
            changed = bool(previous and previous["fingerprint"] != fingerprint)
            status = "ok"
        except Exception as exc:
            status, error = "error", clean(str(exc), 500)
            LOG.warning("%s: %s", name, error)
        with db:
            db.execute("""INSERT INTO observations
                (source_url, source_name, checked_at, status, final_url, fingerprint, data_json, error, changed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (url, name, checked, status, final_url, fingerprint, payload, error, int(changed)))
            db.execute("""DELETE FROM observations WHERE source_url=? AND id NOT IN
                (SELECT id FROM observations WHERE source_url=? ORDER BY id DESC LIMIT ?)""", (url, url, keep))
        results.append(dict(name=name, url=url, checked_at=checked, status=status, final_url=final_url,
                            changed=changed, data=json.loads(payload) if payload else None, error=error))
    return {"checked_at": datetime.now(timezone.utc).isoformat(), "sources": results}


def write_export(path: Path, result: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--db", type=Path, default=Path("data/competitors.sqlite3"))
    parser.add_argument("--output", type=Path, default=Path("data/competitors_latest.json"))
    parser.add_argument("--watch", action="store_true", help="Repeat until stopped; default is one run")
    parser.add_argument("--interval", type=int, default=21600, help="Seconds between completed runs (minimum 60)")
    parser.add_argument("--keep", type=int, default=120, help="Observations retained per source")
    args = parser.parse_args()
    if args.interval < 60 or args.keep < 2:
        parser.error("--interval must be >= 60 and --keep must be >= 2")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        sources = load_sources(args.sources)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    db = open_store(args.db)
    try:
        while True:
            result = run_once(sources, db, PublicFetcher(), args.keep)
            write_export(args.output, result)
            successes = sum(row["status"] == "ok" for row in result["sources"])
            LOG.info("Parsed %s/%s sources; export: %s", successes, len(sources), args.output)
            if not args.watch:
                return 0 if successes == len(sources) else 1
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
