"""Markdown export — matches the format described in spec §4.4.

The pipeline output uses the structure:
    prop_args: [{thesis: str, mechanisms: [str, ...]}, ...]
We render each thesis in italics and each mechanism as a numbered list item,
preserving the inline "(1)... (2)..." sub-reasons that BP matter files use.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

CATEGORY_ORDER = ["IR", "Econ", "Business"]
CATEGORY_HEADERS = {
    "IR": "International Relations",
    "Econ": "Economics",
    "Business": "Business",
}

_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def _format_date_safe(iso: str | None) -> str:
    """Cross-platform date formatter (Windows lacks `%-d`)."""
    if not iso:
        return ""
    m = _DATE_RE.match(iso)
    if not m:
        return iso
    try:
        dt = datetime.strptime(m.group(1), "%Y-%m-%d")
        return f"{dt.strftime('%B')} {dt.day}, {dt.year}"
    except ValueError:
        return iso


def _render_args(side_args: list[dict]) -> list[str]:
    out: list[str] = []
    for arg in side_args or []:
        thesis = (arg.get("thesis") or "").strip()
        if thesis:
            out.append(f"*Thesis: {thesis}*")
            out.append("")
        for i, mech in enumerate(arg.get("mechanisms") or [], start=1):
            mech_str = (mech or "").strip()
            if not mech_str:
                continue
            out.append(f"{i}) {mech_str}")
            out.append("")
    return out


def _render_card(card: dict, notes: str) -> list[str]:
    title = card.get("title") or "(untitled)"
    source = card.get("source") or ""
    pub = _format_date_safe(card.get("published"))
    byline = " · ".join(x for x in [source, pub] if x)

    lines: list[str] = [f"### {title}"]
    if byline:
        lines.append(f"*{byline}*")
    lines.append("")

    if card.get("background"):
        lines += ["**Background:**", card["background"].strip(), ""]

    if card.get("prop_args"):
        lines.append("**Proposition:**")
        lines.append("")
        lines += _render_args(card["prop_args"])

    if card.get("opp_args"):
        lines.append("**Opposition:**")
        lines.append("")
        lines += _render_args(card["opp_args"])

    if card.get("weighing"):
        lines += ["**Weighing:**", card["weighing"].strip(), ""]

    if card.get("data_points"):
        lines.append("**Useful data points:**")
        for dp in card["data_points"]:
            lines.append(f"- {dp}")
        lines.append("")

    if card.get("stock_connections"):
        lines.append(
            "**Stock arguments:** " + ", ".join(card["stock_connections"])
        )
        lines.append("")

    if card.get("motion_areas"):
        lines.append("**Potential motions:**")
        for m in card["motion_areas"]:
            lines.append(f"- {m}")
        lines.append("")

    if card.get("url"):
        lines.append(f"**Source:** {card['url']}")
        lines.append("")

    if notes and notes.strip():
        lines += ["**Personal notes:**", notes.strip(), ""]

    lines.append("---")
    lines.append("")
    return lines


def render_matter_file(entries: list[dict]) -> str:
    """Group entries by category, render H2 sections then per-card H3 blocks."""
    today = datetime.now(timezone.utc)
    header = [
        "# Debate Matter File",
        f"Generated: {today.strftime('%B')} {today.day}, {today.year}",
        "",
        "---",
        "",
    ]

    grouped: dict[str, list[dict]] = {k: [] for k in CATEGORY_ORDER}
    misc: list[dict] = []
    for entry in entries:
        card = entry.get("card_data") or {}
        cat = card.get("category")
        if cat in grouped:
            grouped[cat].append(entry)
        else:
            misc.append(entry)

    body: list[str] = []
    for cat in CATEGORY_ORDER:
        bucket = grouped[cat]
        if not bucket:
            continue
        body.append(f"## {CATEGORY_HEADERS[cat]}")
        body.append("")
        for entry in bucket:
            body += _render_card(entry["card_data"], entry.get("notes", ""))

    if misc:
        body.append("## Other")
        body.append("")
        for entry in misc:
            body += _render_card(entry["card_data"], entry.get("notes", ""))

    if not body:
        body = ["*No saved entries yet.*", ""]

    return "\n".join(header + body)
