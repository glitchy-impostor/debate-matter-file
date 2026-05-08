"""One-time backfill: empty state, process every entry RSS feeds expose.

The standard pipeline is shared via `pipeline.run(initial_state=...)`. The only
backfill-specific concern is the OpenAI rate limit budget — spec calls for ≤5
articles/min, i.e. 12s between mini calls.

Usage:
    OPENAI_API_KEY=sk-... python scripts/backfill.py
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dedupe as dedupe_mod
import pipeline
import utils

log = logging.getLogger("backfill")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the digest with all RSS history.")
    parser.add_argument(
        "--api-delay",
        type=float,
        default=12.0,
        help="Seconds between Stage-2 mini calls (default 12 == 5/min).",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=None,
        help="Cap total articles for a quick smoke test.",
    )
    parser.add_argument(
        "--keep-state",
        action="store_true",
        help="Use existing state.json instead of starting empty (resume mode).",
    )
    parser.add_argument(
        "--dedup-threshold",
        type=float,
        default=dedupe_mod.DEFAULT_THRESHOLD,
        help=(
            "Jaccard threshold for cross-source dedup (default 0.55). "
            "Lower = more aggressive merging. 1.0 disables dedup."
        ),
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    initial_state = utils.load_state() if args.keep_state else {"processed": {}}
    log.info(
        "starting backfill (keep_state=%s, api_delay=%.1fs, max_articles=%s)",
        args.keep_state,
        args.api_delay,
        args.max_articles,
    )

    summary = pipeline.run(
        initial_state=initial_state,
        max_articles=args.max_articles,
        api_delay=args.api_delay,
        dedup_threshold=args.dedup_threshold,
    )
    log.info("backfill summary: %s", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
