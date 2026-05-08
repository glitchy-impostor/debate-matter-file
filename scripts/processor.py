"""Two-stage LLM pipeline:

Stage 1 — GPT-5.4 Nano: cheap relevance filter, batched 10-15 articles per call.
Stage 2 — GPT-5.4 Mini: full BP-debate-framed analysis, one call per surviving article.

Models, prompts, parameters, and output schema follow debate-digest-spec-v3.md
sections 2.4 and 2.5.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

from openai import OpenAI

log = logging.getLogger(__name__)

NANO_MODEL = "gpt-5.4-nano"
MINI_MODEL = "gpt-5.4-mini"

NANO_BATCH_SIZE = 12
NANO_TEMPERATURE = 0.1
NANO_MAX_TOKENS = 1000

MINI_TEMPERATURE = 0.4
MINI_MAX_TOKENS = 2000

REQUIRED_MINI_FIELDS = (
    "title",
    "background",
    "prop_args",
    "opp_args",
    "weighing",
    "stock_connections",
    "motion_areas",
    "data_points",
)


_client: OpenAI | None = None


def client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        _client = OpenAI(api_key=api_key)
    return _client


# ---- Stage 1: Nano relevance filter -------------------------------------

NANO_SYSTEM = """You are a relevance filter for a competitive British Parliamentary (BP) debate research pipeline. Your job is to decide which news articles are worth deep analysis for debate prep.

An article is RELEVANT if it involves:
- International relations, geopolitics, diplomacy, conflict, sanctions, treaties
- Macroeconomic policy, trade, development, monetary/fiscal policy, structural reform
- Significant business/industry moves with policy implications (mergers with antitrust angles, tech regulation, labor disputes)
- Social policy with debatable dimensions (healthcare reform, education policy, criminal justice)
- Environmental/climate policy with economic or geopolitical stakes

An article is IRRELEVANT if it is:
- Routine corporate earnings with no broader policy angle
- Celebrity/entertainment news
- Local crime or human interest stories
- Sports results
- Product launches or marketing
- Incremental updates on already-covered stories with no new substantive development

For each article, output a JSON object:
{
  "url": "the article URL",
  "relevant": true/false,
  "category": "IR" | "Econ" | "Business" | null,
  "region": "specific region(s)" | null,
  "skip_reason": "one-line reason if irrelevant" | null
}

Respond ONLY with a JSON array. No markdown, no preamble."""


def _excerpt(text: str, words: int = 200) -> str:
    return " ".join(text.split()[:words])


def _extract_json(raw: str) -> Any:
    """Tolerant JSON extraction that strips ```json fences if the model adds them."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # last-ditch: pull out the first balanced JSON value
        match = re.search(r"(\{.*\}|\[.*\])", raw, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(1))


def filter_relevance(articles: list[dict]) -> list[dict]:
    """Stage 1. articles is a list of dicts with title/source/url/text fields.

    Returns the input list with extra `_relevance` payload merged into each
    *relevant* article. Irrelevant articles are dropped.
    """
    surviving: list[dict] = []
    for i in range(0, len(articles), NANO_BATCH_SIZE):
        batch = articles[i : i + NANO_BATCH_SIZE]
        result = _call_nano(batch)
        result_by_url = {item.get("url"): item for item in result if isinstance(item, dict)}
        for art in batch:
            verdict = result_by_url.get(art["url"])
            if not verdict:
                log.warning("nano: no verdict for %s", art["url"])
                continue
            if verdict.get("relevant"):
                art["_relevance"] = {
                    "category": verdict.get("category") or art.get("default_category"),
                    "region": verdict.get("region"),
                }
                surviving.append(art)
            else:
                log.info(
                    "nano dropped: %s -- %s",
                    art["title"][:80],
                    verdict.get("skip_reason"),
                )
    log.info("nano filter: %d -> %d", len(articles), len(surviving))
    return surviving


def _call_nano(batch: list[dict]) -> list[dict]:
    lines = []
    for idx, art in enumerate(batch, start=1):
        lines.append(f"{idx}. {art['title']} — {art['source']} — {art['url']}")
        lines.append(_excerpt(art["text"], 200))
        lines.append("")
    user_prompt = "Filter these articles for debate relevance:\n\n" + "\n".join(lines)
    try:
        resp = client().chat.completions.create(
            model=NANO_MODEL,
            temperature=NANO_TEMPERATURE,
            max_completion_tokens=NANO_MAX_TOKENS,
            messages=[
                {"role": "system", "content": NANO_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as exc:
        log.error("nano call failed: %s", exc)
        return []
    raw = resp.choices[0].message.content or ""
    try:
        data = _extract_json(raw)
    except json.JSONDecodeError as exc:
        log.error("nano returned non-JSON: %s -- raw: %s", exc, raw[:300])
        return []
    if not isinstance(data, list):
        log.error("nano did not return a list: %r", type(data))
        return []
    return data


# ---- Stage 2: Mini full analysis ----------------------------------------

MINI_SYSTEM = """You are a research assistant for a competitive British Parliamentary (BP) debater. Your job is to transform news articles into structured debate ammunition — the kind of material that wins extensions in closing half.

Your output must match the style of competitive BP matter files: numbered mechanism chains with clear causal logic, specific data points, and argument structures that can be deployed mid-round.

For each article, output a JSON object with EXACTLY these fields:

{
  "title": "Debate-relevant headline — frame it as the debatable tension, not the newspaper headline. e.g., 'EU Carbon Tariffs Force ASEAN Into Retaliatory Trade Bloc' not 'EU Passes New Climate Legislation'",

  "source": "Publication name",
  "url": "Original URL",
  "published": "ISO 8601 date string",

  "category": "IR" | "Econ" | "Business",
  "region": "Specific region(s) affected, e.g., 'EU / Southeast Asia', 'Sub-Saharan Africa', 'Global'",

  "background": "2-4 sentence factual context. Include specific numbers, dates, actors. This is the 'fast facts' a debater reads to orient themselves. No analysis — just what happened and the relevant context.",

  "prop_args": [
    {
      "thesis": "Clear one-sentence claim that could be a team line.",
      "mechanisms": [
        "First, [mechanism]. This is because (1) ... (2) ... (3) ...",
        "Second, [mechanism]. Three reasons: one, ... two, ... three, ...",
        "Third, [impact/weighing]. This matters because ..."
      ]
    }
  ],

  "opp_args": [
    {
      "thesis": "Clear one-sentence counter-claim.",
      "mechanisms": [
        "First, [mechanism with numbered sub-reasons]",
        "Second, [mechanism with numbered sub-reasons]"
      ]
    }
  ],

  "weighing": "1-2 sentences on what the key clash is and which side has structural advantages. Use weighing language: 'The biggest delta in this debate is...', 'This argument wins because...'",

  "stock_connections": ["List of stock debate arguments this connects to, e.g., 'Dutch Disease', 'Moral Hazard', 'Democratic Backsliding', 'Race to the Bottom', 'Brain Drain', 'Resource Curse', 'Dependency Theory', 'Structural Adjustment'"],

  "motion_areas": [
    "TH, as X, would Y",
    "THBT developing nations should...",
    "THP a world where..."
  ],

  "data_points": [
    "Specific quotable statistics or facts useful mid-round, e.g., '$12B ASEAN export exposure to EU carbon tariffs', 'Oil accounts for 90% of Equatorial Guinea GDP'"
  ]
}

IMPORTANT QUALITY GUIDELINES:
- Mechanisms must have NUMBERED sub-reasons (one, two, three...) with specific causal chains. "This could destabilize the region" is WORTHLESS. "This destabilizes the region because (1) it undermines the existing security architecture by..., (2) it creates a precedent that..." is useful.
- Prop and Opp arguments should be roughly balanced. A debater needs BOTH sides.
- Data points should be specific and citable. Vague statistics are worse than none.
- Motion areas should be plausible tournament motions, not absurdly specific.
- Stock connections should only list genuinely applicable stock arguments — don't force connections.
- If the article somehow doesn't have enough substance for meaningful debate analysis despite passing the relevance filter, set a field "skip": true and provide only title, source, url, and a one-line "skip_reason".

Respond ONLY with the JSON object. No markdown fences, no preamble."""


def analyze_article(article: dict, retries: int = 2) -> dict | None:
    """Stage 2. Returns the parsed card dict, or None if skipped/failed.

    The returned dict has the upstream id, source, and url stamped onto it
    (LLM-supplied source/url are overridden because we know them authoritatively).
    """
    relevance = article.get("_relevance", {})
    user_prompt = (
        "Analyze this article for BP debate prep:\n\n"
        f"Title: {article['title']}\n"
        f"Source: {article['source']}\n"
        f"Published: {article.get('published') or 'unknown'}\n"
        f"URL: {article['url']}\n"
        f"Pre-assigned category: {relevance.get('category') or article.get('default_category')}\n"
        f"Pre-assigned region: {relevance.get('region') or 'unknown'}\n\n"
        "Full text:\n"
        f"{article['text']}"
    )

    for attempt in range(retries + 1):
        try:
            resp = client().chat.completions.create(
                model=MINI_MODEL,
                temperature=MINI_TEMPERATURE,
                max_completion_tokens=MINI_MAX_TOKENS,
                messages=[
                    {"role": "system", "content": MINI_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as exc:
            log.warning("mini call failed (attempt %d): %s", attempt + 1, exc)
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            return None

        raw = resp.choices[0].message.content or ""
        try:
            data = _extract_json(raw)
        except json.JSONDecodeError as exc:
            log.warning(
                "mini returned non-JSON (attempt %d): %s -- raw[:200]=%s",
                attempt + 1,
                exc,
                raw[:200],
            )
            if attempt < retries:
                continue
            return None

        if not isinstance(data, dict):
            log.warning("mini returned non-object: %r", type(data))
            return None

        if data.get("skip"):
            log.info("mini skipped %s: %s", article["url"], data.get("skip_reason"))
            return None

        missing = [f for f in REQUIRED_MINI_FIELDS if f not in data]
        if missing:
            log.warning("mini output missing fields %s for %s", missing, article["url"])
            if attempt < retries:
                continue
            return None

        # Authoritative stamping — never trust the model's url/source/published.
        data["source"] = article["source"]
        data["url"] = article["url"]
        if article.get("published"):
            data["published"] = article["published"]
        if not data.get("category"):
            data["category"] = relevance.get("category") or article.get("default_category")
        if not data.get("region"):
            data["region"] = relevance.get("region")
        return data

    return None
