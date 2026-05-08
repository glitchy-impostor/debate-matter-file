"""Article text extraction with trafilatura and a fallback chain."""
from __future__ import annotations

import logging
import random
import re
import time
from html import unescape

import trafilatura

log = logging.getLogger(__name__)

MIN_WORDS = 50
FETCH_DELAY_RANGE = (1.0, 2.0)


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
