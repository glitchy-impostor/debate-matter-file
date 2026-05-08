"""Free diagnostic run — see why articles do or don't get through extraction.

For each entry from each feed, prints:
    feed | url | resolved? | trafilatura words | rss-fallback words | verdict

Verdict is one of: OK (would go to LLM), SKIP (below MIN_WORDS), or RESOLVE_FAIL.

Does NOT call OpenAI, does NOT touch state.json, does NOT write any cards.
Use this to verify which feeds yield usable content before paying for an LLM run.

Usage:
    python scripts/diagnose.py                  # 5 articles per feed
    python scripts/diagnose.py --per-feed 3
    python scripts/diagnose.py --feed BBC       # only feeds whose name contains "BBC"
    python scripts/diagnose.py --gnews          # also test the disabled Google News feeds
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import extractor
import feeds as feeds_mod

log = logging.getLogger("diagnose")


def shorten(s: str, n: int = 70) -> str:
    if not s:
        return ""
    s = s.replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def diagnose_entry(entry: dict) -> dict:
    original = entry["link"]
    resolved = extractor.resolve_url(original)
    resolution = "same" if resolved == original else "→ " + resolved

    # Try trafilatura on resolved URL
    text = extractor.extract(resolved, rss_content="", rss_summary="")
    traf_words = extractor.word_count(text or "")

    # Independently measure RSS fallback word counts so we know how thin sources are.
    fb_content = extractor._strip_html(entry.get("content", ""))
    fb_summary = extractor._strip_html(entry.get("summary", ""))
    rss_words = max(extractor.word_count(fb_content), extractor.word_count(fb_summary))

    if "news.google.com" in resolved:
        verdict = "RESOLVE_FAIL"
    elif text and traf_words >= extractor.MIN_WORDS:
        verdict = "OK (trafilatura)"
    elif rss_words >= extractor.MIN_WORDS:
        verdict = "OK (rss-fallback)"
    else:
        verdict = "SKIP"

    return {
        "feed": entry["feed_name"],
        "title": shorten(entry["title"], 60),
        "url": shorten(original, 60),
        "resolution": shorten(resolution, 60),
        "traf_words": traf_words,
        "rss_words": rss_words,
        "verdict": verdict,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnostic dry-run (no LLM calls).")
    parser.add_argument("--per-feed", type=int, default=5, help="Entries per feed to test.")
    parser.add_argument(
        "--feed",
        action="append",
        default=[],
        help="Only test feeds whose name contains this substring (repeatable).",
    )
    parser.add_argument(
        "--gnews",
        action="store_true",
        help="Also include the Google News-routed feeds (Reuters/AP/Times).",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.gnews:
        os.environ["DEBATE_DIGEST_USE_GNEWS"] = "1"
        # rebuild FEEDS now that the env var is set
        feeds_mod.FEEDS = feeds_mod._active_feeds()

    feeds = feeds_mod.FEEDS
    if args.feed:
        needles = [n.lower() for n in args.feed]
        feeds = [f for f in feeds if any(n in f.name.lower() for n in needles)]
    if not feeds:
        print("No feeds match.")
        return 1

    rows: list[dict] = []
    counts = {"OK (trafilatura)": 0, "OK (rss-fallback)": 0, "SKIP": 0, "RESOLVE_FAIL": 0}
    for feed in feeds:
        entries = feeds_mod.fetch_entries(feed)[: args.per_feed]
        if not entries:
            print(f"\n[{feed.name}] no entries returned.")
            continue
        print(f"\n[{feed.name}] testing {len(entries)} entries...")
        for entry in entries:
            row = diagnose_entry(entry)
            counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
            rows.append(row)
            print(
                f"  {row['verdict']:18s}  traf={row['traf_words']:>4d}  rss={row['rss_words']:>4d}"
                f"  {row['title']}"
            )
            if row["resolution"] != "same":
                print(f"                       {row['resolution']}")

    print("\n" + "=" * 72)
    total = sum(counts.values())
    print(f"Total tested: {total}")
    for k in ("OK (trafilatura)", "OK (rss-fallback)", "SKIP", "RESOLVE_FAIL"):
        n = counts.get(k, 0)
        pct = 100 * n / total if total else 0
        print(f"  {k:20s}: {n:3d}  ({pct:5.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
