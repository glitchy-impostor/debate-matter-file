"""Main scheduled pipeline.

Orchestrates: load state -> fetch RSS -> dedupe -> extract text -> nano filter
-> mini analysis -> write daily card JSONs -> update state.json + index.json.

Run via GitHub Actions cron (every 3h) or `python scripts/pipeline.py` locally.
"""
from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from pathlib import Path

# allow `python scripts/pipeline.py` from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from dotenv import load_dotenv
    # override=True so a fresh .env beats any stale OS-scope env var
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)
except ImportError:
    pass  # optional; CI uses real env vars

import dedupe as dedupe_mod
import extractor
import feeds
import processor
import utils

log = logging.getLogger("pipeline")


def gather_dirty(state: dict, all_entries: list[dict]) -> list[dict]:
    """Filter out entries already present in state.processed."""
    processed = state.get("processed", {})
    seen_in_run: set[str] = set()
    dirty: list[dict] = []
    for entry in all_entries:
        h = utils.url_hash(entry["link"])
        if h in processed or h in seen_in_run:
            continue
        seen_in_run.add(h)
        dirty.append({**entry, "_hash": h})
    return dirty


def extract_texts(dirty: list[dict], rate_limit: bool = True) -> list[dict]:
    """Resolve any Google News redirects, fetch text, drop articles below the
    word-count threshold. The resolved URL is what ends up in the card so users
    click through to the publisher rather than the GNews trampoline.
    """
    out: list[dict] = []
    total = len(dirty)
    for i, entry in enumerate(dirty):
        resolved_url = extractor.resolve_url(entry["link"])
        if resolved_url != entry["link"]:
            log.debug("gnews resolved: %s -> %s", entry["link"][:80], resolved_url[:80])
        text = extractor.extract(
            resolved_url,
            rss_content=entry.get("content", ""),
            rss_summary=entry.get("summary", ""),
        )
        if text:
            out.append(
                {
                    "title": entry["title"],
                    "url": resolved_url,
                    "source": entry["feed_name"].split(" ", 1)[0],
                    "default_category": entry["default_category"],
                    "published": utils.published_to_iso(entry.get("published_parsed"))
                    or entry.get("published"),
                    "published_parsed": entry.get("published_parsed"),
                    "text": text,
                    "_hash": entry["_hash"],
                }
            )
        if (i + 1) % 25 == 0 or i + 1 == total:
            log.info("extract progress: %d/%d (kept %d)", i + 1, total, len(out))
        if rate_limit and i < total - 1:
            extractor.sleep_between(resolved_url)
    return out


def build_card(article: dict, analysis: dict) -> dict:
    """Combine pipeline metadata with the LLM analysis into a final card record."""
    return {
        "id": utils.card_id(article["url"]),
        "title": analysis.get("title") or article["title"],
        "source": article["source"],
        "url": article["url"],
        "published": analysis.get("published") or article.get("published"),
        "category": analysis.get("category") or article.get("default_category"),
        "region": analysis.get("region"),
        "background": analysis["background"],
        "prop_args": analysis["prop_args"],
        "opp_args": analysis["opp_args"],
        "weighing": analysis["weighing"],
        "stock_connections": analysis.get("stock_connections", []),
        "motion_areas": analysis.get("motion_areas", []),
        "data_points": analysis.get("data_points", []),
    }


def run(
    *,
    initial_state: dict | None = None,
    max_articles: int | None = None,
    api_delay: float = 0.0,
    dedup_threshold: float = dedupe_mod.DEFAULT_THRESHOLD,
) -> dict:
    """Execute one pipeline pass.

    initial_state    — overrides loading state.json (used by backfill).
    max_articles     — cap dirty articles after extraction (debug).
    api_delay        — extra sleep between mini calls (rate-limit safety net).
    dedup_threshold  — Jaccard threshold for cross-source dedup. Set to 1.0 to disable.
    """
    import time

    state = initial_state if initial_state is not None else utils.load_state()
    pruned = utils.prune_state(state)
    if pruned:
        log.info("pruned %d expired state entries", pruned)

    log.info("fetching feeds")
    raw_entries = feeds.fetch_all()
    log.info("total raw entries: %d", len(raw_entries))

    dirty = gather_dirty(state, raw_entries)
    log.info("dirty (unprocessed): %d", len(dirty))
    if max_articles is not None:
        dirty = dirty[:max_articles]
        log.info("capped to %d for this run", len(dirty))
    if not dirty:
        utils.save_state(state)
        utils.update_index()
        return {"new_cards": 0, "dirty": 0, "filtered_in": 0}

    log.info("extracting article text")
    articles = extract_texts(dirty)
    log.info("articles with usable text: %d", len(articles))

    if articles and dedup_threshold < 1.0:
        kept, dropped = dedupe_mod.dedupe(articles, threshold=dedup_threshold)
        for dup, rep, sim in dropped:
            log.info(
                "dedup: drop %s (sim=%.2f, matches %s)",
                dup.get("title", "")[:70],
                sim,
                rep.get("title", "")[:70],
            )
        log.info("after dedup: %d -> %d (dropped %d)", len(articles), len(kept), len(dropped))
        articles = kept

    if not articles:
        # mark all dirty as processed even if extraction failed — do not re-attempt forever
        for entry in dirty:
            state["processed"][entry["_hash"]] = {
                "url": entry["link"],
                "source": entry["feed_name"],
                "processed_at": utils.now_utc_iso(),
            }
        utils.save_state(state)
        utils.update_index()
        return {"new_cards": 0, "dirty": len(dirty), "filtered_in": 0}

    log.info("stage 1: nano relevance filter")
    relevant = processor.filter_relevance(articles)

    log.info("stage 2: mini analysis on %d survivors", len(relevant))
    cards_by_date: dict[str, list[dict]] = defaultdict(list)
    for i, article in enumerate(relevant):
        analysis = processor.analyze_article(article)
        if not analysis:
            continue
        card = build_card(article, analysis)
        date_str = utils.published_to_date(
            article.get("published_parsed"), card.get("published")
        )
        cards_by_date[date_str].append(card)
        if api_delay and i < len(relevant) - 1:
            time.sleep(api_delay)

    new_cards_total = 0
    for date_str, cards in cards_by_date.items():
        added = utils.append_cards_for_date(date_str, cards)
        log.info("wrote %d cards to %s (added %d new)", len(cards), date_str, added)
        new_cards_total += added

    # Mark every dirty entry as processed — even ones the filters dropped — so
    # we don't pay nano/mini costs for them again.
    for entry in dirty:
        state["processed"][entry["_hash"]] = {
            "url": entry["link"],
            "source": entry["feed_name"],
            "processed_at": utils.now_utc_iso(),
        }
    utils.save_state(state)
    utils.update_index()

    return {
        "new_cards": new_cards_total,
        "dirty": len(dirty),
        "filtered_in": len(relevant),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the debate-digest pipeline once.")
    parser.add_argument("--max-articles", type=int, default=None, help="Cap articles processed.")
    parser.add_argument(
        "--api-delay",
        type=float,
        default=0.0,
        help="Sleep this many seconds between Stage-2 calls.",
    )
    parser.add_argument(
        "--dedup-threshold",
        type=float,
        default=dedupe_mod.DEFAULT_THRESHOLD,
        help=(
            "Jaccard threshold for cross-source dedup (default 0.55). "
            "Lower = more aggressive merging. 1.0 disables dedup entirely."
        ),
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    summary = run(
        max_articles=args.max_articles,
        api_delay=args.api_delay,
        dedup_threshold=args.dedup_threshold,
    )
    log.info("summary: %s", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
