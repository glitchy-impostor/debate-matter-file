"""Article text extraction with trafilatura and a fallback chain."""
from __future__ import annotations

import base64
import logging
import random
import re
import time
from html import unescape

import requests
import trafilatura

log = logging.getLogger(__name__)

MIN_WORDS = 50
FETCH_DELAY_RANGE = (1.0, 2.0)
RESOLVE_TIMEOUT = 15
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _strip_html(text: str) -> str:
    """Cheap HTML strip for fallback to RSS content/summary fields."""
    if not text:
        return ""
    text = re.sub(r"(?is)<script.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def word_count(text: str) -> int:
    return len(text.split()) if text else 0


def _decode_gnews_path(encoded: str) -> str | None:
    """Try to recover the publisher URL from the base64 article-id path.

    Google News /rss/articles/<id> paths are base64url-encoded protobuf-ish
    blobs that often contain the original URL as a length-prefixed string.
    Not always — newer encodings need server-side resolution — so this is a
    best-effort fast path; resolve_via_fetch handles the rest.
    """
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        raw = base64.urlsafe_b64decode(padded)
    except Exception:
        return None
    text = raw.decode("latin-1", errors="ignore")
    match = re.search(r"https?://[^\s\x00-\x1f\x7f-\xff'\"<>]+", text)
    if not match:
        return None
    candidate = re.sub(r"[^A-Za-z0-9/._~?&=#%:\-]+$", "", match.group(0))
    if "news.google.com" in candidate or len(candidate) < 15:
        return None
    return candidate


def _resolve_via_fetch(url: str) -> str | None:
    """Hit the Google News page and pull the publisher URL out of the HTML."""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=RESOLVE_TIMEOUT,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        log.debug("gnews fetch failed: %s -> %s", url, exc)
        return None
    if "news.google.com" not in resp.url:
        return resp.url
    html = resp.text
    for pattern in (
        r'data-n-au="([^"]+)"',
        r'data-n-cdaid="([^"]+)"',
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']',
        r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']',
    ):
        m = re.search(pattern, html)
        if not m:
            continue
        candidate = m.group(1)
        if "news.google.com" not in candidate and candidate.startswith("http"):
            return candidate
    return None


def resolve_url(url: str) -> str:
    """If `url` is a Google News redirect, return the publisher URL; else return as-is."""
    if "news.google.com" not in url:
        return url
    path_match = re.search(r"/articles/([^?/]+)", url)
    if path_match:
        decoded = _decode_gnews_path(path_match.group(1))
        if decoded:
            return decoded
    fetched = _resolve_via_fetch(url)
    return fetched or url


def extract(url: str, rss_content: str = "", rss_summary: str = "") -> str | None:
    """Try trafilatura first, then RSS content, then RSS summary.

    Returns extracted text or None if nothing meets the MIN_WORDS threshold.
    Pipeline-level rate limiting is the caller's responsibility — call sleep_between()
    between successive extract() calls.
    """
    text = ""
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            extracted = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=True,
                favor_recall=True,
            )
            if extracted:
                text = extracted.strip()
    except Exception as exc:  # trafilatura raises a variety of network errors
        log.warning("trafilatura failed for %s: %s", url, exc)

    if word_count(text) >= MIN_WORDS:
        return text

    fallback = _strip_html(rss_content)
    if word_count(fallback) >= MIN_WORDS:
        log.info("using RSS content fallback for %s", url)
        return fallback

    fallback = _strip_html(rss_summary)
    if word_count(fallback) >= MIN_WORDS:
        log.info("using RSS summary fallback for %s", url)
        return fallback

    log.info("article below %d-word threshold, skipping: %s", MIN_WORDS, url)
    return None


def sleep_between() -> None:
    """1-2 second jittered delay between fetches to avoid hammering sources."""
    time.sleep(random.uniform(*FETCH_DELAY_RANGE))
