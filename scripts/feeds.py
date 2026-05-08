"""RSS feed definitions and validation.

Two tiers of sources:

* PRIMARY  — direct publisher RSS feeds with substantive RSS content. These
  produce reliable cards because trafilatura has a real article URL to work
  with, or because the RSS summary itself is long enough to clear MIN_WORDS.

* SECONDARY (Google News-routed) — Reuters / AP / Times via Google News
  search. The redirector encodes the publisher URL in a way that's hostile to
  extraction; we skip these by default. Enable by setting
  DEBATE_DIGEST_USE_GNEWS=1 once a working resolver is in place.
"""
from __future__ import annotations

import calendar
import logging
import os
import time
from dataclasses import dataclass

import feedparser
import requests

log = logging.getLogger(__name__)

# Drop RSS entries older than this. Some feeds (Economist, Project Syndicate)
# return 300 entries going back years; we don't want to re-process all of that
# every cron run. Override with DEBATE_DIGEST_MAX_AGE_DAYS=N if you need to.
MAX_AGE_DAYS = int(os.environ.get("DEBATE_DIGEST_MAX_AGE_DAYS", "14"))


@dataclass(frozen=True)
class Feed:
    name: str
    url: str
    default_category: str
    default_region: str | None = None


PRIMARY_FEEDS: list[Feed] = [
    # Open-content news
    Feed("BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml", "IR"),
    Feed("BBC Business", "http://feeds.bbci.co.uk/news/business/rss.xml", "Business"),
    Feed("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "IR"),
    Feed("Guardian World", "https://www.theguardian.com/world/rss", "IR"),
    Feed("Guardian Business", "https://www.theguardian.com/business/rss", "Business"),
    Feed("NPR World", "https://feeds.npr.org/1004/rss.xml", "IR"),
    # IR / policy
    Feed("Foreign Policy", "https://foreignpolicy.com/feed/", "IR"),
    Feed("The Diplomat", "https://thediplomat.com/feed/", "IR"),
    Feed(
        "Project Syndicate",
        "https://www.project-syndicate.org/rss",
        "Econ",
    ),
    Feed(
        "Atlantic Ideas",
        "https://www.theatlantic.com/feed/channel/ideas/",
        "IR",
    ),
    Feed(
        "Atlantic Politics",
        "https://www.theatlantic.com/feed/channel/politics/",
        "IR",
    ),
    # Bloomberg — paywalled but RSS summaries tend to be substantive
    Feed(
        "Bloomberg Politics",
        "https://feeds.bloomberg.com/politics/news.rss",
        "IR",
    ),
    Feed(
        "Bloomberg Economics",
        "https://feeds.bloomberg.com/economics/news.rss",
        "Econ",
    ),
    # Enriched paywalled — RSS summaries usually clear MIN_WORDS
    Feed(
        "Economist International",
        "https://www.economist.com/international/rss.xml",
        "IR",
    ),
    Feed(
        "Economist Finance",
        "https://www.economist.com/finance-and-economics/rss.xml",
        "Econ",
    ),
    Feed("WSJ World", "https://feeds.a.dj.com/rss/RSSWorldNews.xml", "IR"),
    Feed("WSJ Business", "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml", "Business"),
]

# Disabled by default — Google News redirectors are unreliable to resolve.
# Enable with: $env:DEBATE_DIGEST_USE_GNEWS = "1"
SECONDARY_GNEWS_FEEDS: list[Feed] = [
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
    Feed(
        "Times World",
        "https://news.google.com/rss/search?q=site:thetimes.com+world&hl=en-GB&gl=GB&ceid=GB:en",
        "IR",
    ),
]


def _active_feeds() -> list[Feed]:
    feeds = list(PRIMARY_FEEDS)
    if os.environ.get("DEBATE_DIGEST_USE_GNEWS") == "1":
        feeds.extend(SECONDARY_GNEWS_FEEDS)
    return feeds


FEEDS: list[Feed] = _active_feeds()


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

    cutoff = time.time() - MAX_AGE_DAYS * 86400 if MAX_AGE_DAYS > 0 else 0
    out: list[dict] = []
    skipped_old = 0
    for entry in parsed.entries:
        link = entry.get("link")
        title = entry.get("title")
        if not link or not title:
            continue
        published_parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        if cutoff and published_parsed:
            try:
                ts = calendar.timegm(published_parsed)
            except (TypeError, ValueError):
                ts = 0
            if ts and ts < cutoff:
                skipped_old += 1
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
                "published_parsed": published_parsed,
            }
        )
    if skipped_old:
        log.info("dropped %d entries older than %dd from %s", skipped_old, MAX_AGE_DAYS, feed.name)
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
