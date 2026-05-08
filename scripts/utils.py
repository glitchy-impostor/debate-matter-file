"""Hashing, state.json management, date helpers, atomic JSON writes."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = REPO_ROOT / "state.json"
DATA_DIR = REPO_ROOT / "data"
CARDS_DIR = DATA_DIR / "cards"
INDEX_FILE = DATA_DIR / "index.json"

PRUNE_DAYS = 30


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def card_id(url: str) -> str:
    """Short, stable card id derived from the article URL."""
    return url_hash(url)[:12]


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # tolerate trailing Z
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def published_to_iso(published_parsed) -> str | None:
    """Convert feedparser's time.struct_time into ISO 8601 UTC."""
    if not published_parsed:
        return None
    try:
        dt = datetime(*published_parsed[:6], tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return None


def published_to_date(published_parsed, fallback_iso: str | None = None) -> str:
    """Return YYYY-MM-DD for grouping. Falls back to today UTC."""
    if published_parsed:
        try:
            return datetime(*published_parsed[:6], tzinfo=timezone.utc).strftime("%Y-%m-%d")
        except (TypeError, ValueError):
            pass
    if fallback_iso:
        dt = parse_iso(fallback_iso)
        if dt:
            return dt.strftime("%Y-%m-%d")
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ---- state.json ---------------------------------------------------------


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {"processed": {}}
    try:
        with STATE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if "processed" not in data:
            data["processed"] = {}
        return data
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("state.json unreadable, starting fresh: %s", exc)
        return {"processed": {}}


def prune_state(state: dict[str, Any], days: int = PRUNE_DAYS) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    processed = state.get("processed", {})
    drop_keys = []
    for key, entry in processed.items():
        ts = parse_iso(entry.get("processed_at"))
        if ts is None or ts < cutoff:
            drop_keys.append(key)
    for k in drop_keys:
        processed.pop(k, None)
    return len(drop_keys)


def save_state(state: dict[str, Any]) -> None:
    write_json_atomic(STATE_FILE, state)


# ---- atomic JSON --------------------------------------------------------


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


# ---- card storage -------------------------------------------------------


def append_cards_for_date(date_str: str, new_cards: list[dict]) -> int:
    """Merge new_cards into data/cards/<date>.json, deduping by card id."""
    if not new_cards:
        return 0
    path = CARDS_DIR / f"{date_str}.json"
    existing = read_json(path, default={"date": date_str, "last_updated": None, "cards": []})
    by_id = {c["id"]: c for c in existing.get("cards", [])}
    added = 0
    for card in new_cards:
        if card["id"] not in by_id:
            by_id[card["id"]] = card
            added += 1
        else:
            # update fields if re-processed
            by_id[card["id"]] = card
    existing["date"] = date_str
    existing["last_updated"] = now_utc_iso()
    existing["cards"] = sorted(by_id.values(), key=lambda c: c.get("published") or "", reverse=True)
    write_json_atomic(path, existing)
    return added


def update_index() -> dict[str, Any]:
    """Regenerate data/index.json from the cards directory."""
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(CARDS_DIR.glob("*.json"), reverse=True)
    dates: list[str] = []
    total = 0
    for f in files:
        data = read_json(f, default=None)
        if not data:
            continue
        date_str = data.get("date") or f.stem
        dates.append(date_str)
        total += len(data.get("cards", []))
    index = {
        "dates": dates,
        "total_cards": total,
        "last_updated": now_utc_iso(),
    }
    write_json_atomic(INDEX_FILE, index)
    return index
