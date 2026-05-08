"""RSS feed definitions and validation.

Feed list was validated 2026-05-07. Reuters and AP discontinued their direct
RSS feeds; both are routed through Google News search RSS as a stable proxy.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import feedparser
import requests

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Feed:
    name: str
    url: str
    default_category: str
    default_region: str | None = None


FEEDS: list[Feed] = [
    Feed("BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml", "IR"),
    Feed("BBC Business", "http://feeds.bbci.co.uk/news/business/rss.xml", "Business"),
    Feed("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "IR"),
    Feed("Guardian World", "https://www.theguardian.com/world/rss", "IR"),
    Feed("Guardian Business", "https://www.theguardian.com/business/rss", "Business"),
    Feed("NPR World", "https://feeds.npr.org/1004/rss.xml", "IR"),
    Feed("Foreign Policy", "https://foreignpolicy.com/feed/", "IR"),
    Feed(
        "Reuters World",
        "https://news.google.com/rss/search?q=site:reuters.com+world&hl=en-US&gl=US&ceid=US:en",
        "IR",
    ),
    Feed(
        "Reuters Business",
        "https://news.google.com/rss/search?q=site:reuters.com+business&hl=en-US&gl=US&ceid=US:en",
        "Business",
    ),
    Feed(
        "AP World",
        "https://news.google.com/rss/search?q=site:apnews.com+world&hl=en-US&gl=US&ceid=US:en",
        "IR",
    ),
    Feed(
        "AP Business",
        "https://news.google.com/rss/search?q=site:apnews.com+business&hl=en-US&gl=US&ceid=US:en",
        "Business",
    ),
]


USER_AGENT = "DebateDigest/1.0 (+https://github.com/)"


def fetch_entries(feed: Feed, timeout: int = 20) -> list[dict]:
    """Fetch a single feed and return its entries as plain dicts.

    feedparser handles malformed XML gracefully and still returns what it can.
    """
    try:
        resp = requests.get(feed.url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.warning("feed fetch failed: %s -> %s", feed.name, exc)
        return []

    parsed = feedparser.parse(resp.content)
    if parsed.bozo and not parsed.entries:
        log.warning("feed parse failed: %s -> %s", feed.name, parsed.bozo_exception)
        return []

    out: list[dict] = []
    for entry in parsed.entries:
        link = entry.get("link")
        title = entry.get("title")
        if not link or not title:
            continue
        out.append(
            {
                "feed_name": feed.name,
                "default_category": feed.default_category,
                "title": title,
                "link": link,
                "summary": entry.get("summary", ""),
                "content": _extract_content_field(entry),
                "published": entry.get("published") or entry.get("updated"),
                "published_parsed": entry.get("published_parsed") or entry.get("updated_parsed"),
            }
        )
    return out


def _extract_content_field(entry) -> str:
    """RSS 'content' field can be missing, a string, or a list of dicts."""
    content = entry.get("content")
    if not content:
        return ""
    if isinstance(content, list):
        return " ".join(c.get("value", "") for c in content if isinstance(c, dict))
    return str(content)


def fetch_all() -> list[dict]:
    """Fetch all configured feeds and return the union of entries."""
    all_entries: list[dict] = []
    for feed in FEEDS:
        entries = fetch_entries(feed)
        log.info("fetched %d entries from %s", len(entries), feed.name)
        all_entries.extend(entries)
    return all_entries


def validate_feeds() -> dict[str, bool]:
    """Quick validation pass — useful for CI sanity checks."""
    results = {}
    for feed in FEEDS:
        try:
            r = requests.get(feed.url, headers={"User-Agent": USER_AGENT}, timeout=15)
            results[feed.name] = r.status_code == 200 and len(r.content) > 100
        except requests.RequestException:
            results[feed.name] = False
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    for name, ok in validate_feeds().items():
        print(f"{'OK ' if ok else 'FAIL'} {name}")
