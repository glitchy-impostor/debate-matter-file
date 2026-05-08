"""Intra-run article deduplication.

Many sources cover the same event with different framings. We keep one article
per cluster, choosing the first occurrence in input order — so callers should
arrange `articles` by preferred source first (open-content sources before
paywalled, etc.).

Heuristic: lowercase the title plus the first ~600 characters of the body,
extract content tokens (≥3 chars, non-stopword), and compute Jaccard
similarity between any two articles. Threshold defaults to 0.55, which is
permissive enough to merge "Trump fires at Iran in Hormuz" with "US Navy
clashes with Iran near Strait of Hormuz" but conservative enough to keep
genuinely different stories apart.
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.55
SIG_BODY_CHARS = 600

# Common English + news-language tokens that don't disambiguate stories.
STOPWORDS = frozenset({
    "the", "a", "an", "of", "for", "in", "on", "to", "and", "or", "as",
    "is", "are", "was", "were", "be", "been", "being", "with", "at", "by",
    "from", "this", "that", "these", "those", "it", "its", "but", "not",
    "so", "has", "have", "had", "will", "would", "could", "should", "may",
    "might", "can", "do", "does", "did", "done", "says", "said", "say",
    "after", "before", "over", "under", "amid", "during", "while", "when",
    "where", "what", "who", "whom", "whose", "why", "how", "new", "newly",
    "report", "reports", "reported", "reporting", "report's",
    "he", "she", "his", "her", "hers", "they", "their", "them", "we",
    "our", "us", "you", "your", "i", "me", "my", "mine",
    "no", "yes", "if", "than", "then", "such", "also", "more", "most",
    "some", "any", "all", "each", "every", "both", "either", "neither",
    "one", "two", "three", "first", "second", "third",
    "very", "much", "many", "few", "several", "between", "among",
    "into", "onto", "off", "out", "up", "down", "back", "out",
    "year", "years", "day", "days", "week", "weeks", "month", "months",
    "today", "yesterday", "tomorrow", "now", "soon",
    "say", "told", "tell", "asked", "ask", "called", "calls", "call",
    "uk", "eu", "wsj",  # 2-letter source/scope tokens that aren't entity-disambiguating
})

WORD_RE = re.compile(r"[a-z0-9]+")


def signature(article: dict) -> frozenset[str]:
    title = article.get("title") or ""
    body = (article.get("text") or "")[:SIG_BODY_CHARS]
    raw = (title + "  " + body).lower()
    return frozenset(
        tok for tok in WORD_RE.findall(raw) if tok not in STOPWORDS and len(tok) > 2
    )


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    return inter / len(a | b)


def dedupe(
    articles: list[dict],
    threshold: float = DEFAULT_THRESHOLD,
) -> tuple[list[dict], list[tuple[dict, dict, float]]]:
    """Cluster `articles`. Returns (kept, dropped_pairs).

    `dropped_pairs` is a list of `(dup, representative, similarity)` so callers
    can log or audit. Input order is treated as priority — first one wins.
    """
    if threshold >= 1.0 or len(articles) < 2:
        return list(articles), []

    kept: list[dict] = []
    sigs: list[frozenset[str]] = []
    dropped: list[tuple[dict, dict, float]] = []

    for art in articles:
        sig = signature(art)
        best_idx, best_sim = -1, 0.0
        for i, prev_sig in enumerate(sigs):
            sim = jaccard(sig, prev_sig)
            if sim > best_sim:
                best_idx, best_sim = i, sim
        if best_idx >= 0 and best_sim >= threshold:
            dropped.append((art, kept[best_idx], best_sim))
            continue
        kept.append(art)
        sigs.append(sig)

    return kept, dropped
