# Debate Digest — System Specification v2

> **Purpose:** This spec is a complete implementation guide. Feed it to Claude Code with: `"Read debate-digest-spec.md and implement the system step by step."`
>
> **What changed from v1:** LLM prompt and card format completely reworked after analyzing actual BP debate matter files. Added trafilatura for full article extraction. Added backfill script. Cards now produce numbered argument chains, prop/opp sketches, and stock argument connections — not shallow summaries. Two-stage LLM pipeline: GPT-5.4 Nano filters for relevance, GPT-5.4 Mini does full debate analysis on survivors only.

---

## 1. System Overview

A pipeline that scrapes free news sources (RSS feeds), extracts full article text, filters for debate relevance via GPT-5.4 Nano, then processes relevant articles through GPT-5.4 Mini with BP debate-oriented framing, and publishes the results as a card-based static site on GitHub Pages. A thin Railway API provides matter file persistence — users can save any card to a curated matter file for tournament prep, then export it as a structured Markdown document matching standard BP matter file conventions.

### Components

```
┌─────────────────────────────────────────────────────────┐
│                   GitHub Actions (Cron)                  │
│  Every 3h: RSS → dedupe → trafilatura → nano filter     │
│  → mini analysis → commit cards JSON to repo            │
└──────────────┬──────────────────────────────────────────┘
               │ git push (data/cards/*.json, state.json)
               ▼
┌─────────────────────────────────────────────────────────┐
│              GitHub Pages (Static Frontend)              │
│  Card-based digest UI │ Matter file viewer │ Archive     │
│  Calls Railway API for matter file CRUD                  │
└──────────────┬──────────────────────────────────────────┘
               │ fetch()
               ▼
┌─────────────────────────────────────────────────────────┐
│              Railway (Thin API)                          │
│  FastAPI + SQLite │ Matter file CRUD │ Export as .md     │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Data Pipeline (GitHub Actions)

### 2.1 RSS Sources

All free, no API keys. Use `feedparser` (Python).

| Source              | Feed URL                                                  | Categories       |
|---------------------|-----------------------------------------------------------|-------------------|
| Reuters World       | `https://feeds.reuters.com/Reuters/worldNews`             | IR                |
| Reuters Business    | `https://feeds.reuters.com/reuters/businessNews`          | Econ, Business    |
| BBC World           | `http://feeds.bbci.co.uk/news/world/rss.xml`              | IR                |
| BBC Business        | `http://feeds.bbci.co.uk/news/business/rss.xml`           | Econ, Business    |
| Al Jazeera          | `https://www.aljazeera.com/xml/rss/all.xml`               | IR                |
| AP News             | `https://rsshub.app/apnews/topics/apf-business`          | Business          |
| The Guardian World  | `https://www.theguardian.com/world/rss`                   | IR                |
| The Guardian Business| `https://www.theguardian.com/business/rss`               | Econ, Business    |
| NPR World           | `https://feeds.npr.org/1004/rss.xml`                     | IR                |
| Foreign Policy      | `https://foreignpolicy.com/feed/`                        | IR                |

**Note:** Some feeds may have changed URLs or gone stale. The first implementation task is to validate each feed and replace dead ones. RSSHub (`rsshub.app`) can proxy many sources that don't have native RSS. Claude Code should check each feed for a 200 response and valid XML before finalizing the list.

### 2.2 Clean/Dirty State Management

File: `state.json` at repo root.

```json
{
  "processed": {
    "<sha256_of_article_url>": {
      "url": "https://...",
      "source": "Reuters",
      "processed_at": "2026-05-07T14:00:00Z"
    }
  }
}
```

**Logic per run:**
1. Pull latest `state.json` from repo
2. Fetch all RSS feeds, extract entries
3. For each entry: `hash = sha256(entry.link)`
4. If hash exists in `state.processed` → **clean**, skip
5. If hash NOT in state → **dirty**, queue for processing
6. Process dirty articles → generate cards
7. Update `state.json` with new hashes
8. Commit both `state.json` and new card data

**Pruning:** Remove entries older than 30 days from `state.json` on each run to prevent unbounded growth.

### 2.3 Article Content Extraction

**Primary method:** Use `trafilatura` to fetch and extract full article text from the source URL. This library handles boilerplate removal, paywall detection, and diverse layouts reliably.

```python
import trafilatura

downloaded = trafilatura.fetch_url(article_url)
text = trafilatura.extract(downloaded, include_comments=False, include_tables=True)
```

**Fallback chain:**
1. `trafilatura.extract()` on fetched page → full article text
2. If trafilatura returns None/empty → use RSS `content` field (sometimes contains extended HTML)
3. If that's also empty → use RSS `summary` field
4. If summary is < 50 words → skip this article entirely (not enough signal for useful debate analysis)

**Rate limiting:** Add a 1-2 second delay between fetches to avoid hammering sources.

### 2.4 LLM Processing (Two-Stage: GPT-5.4 Nano → GPT-5.4 Mini)

The pipeline uses a **two-stage cascade** to balance cost and quality:

1. **Stage 1 — Relevance Filter (GPT-5.4 Nano, $0.20/$1.25 per 1M tokens):** Cheap, fast pass over all dirty articles. Decides whether an article is debate-worthy and assigns category/region. Filters out routine corporate earnings, celebrity news, puff pieces, local crime, etc.

2. **Stage 2 — Full Analysis (GPT-5.4 Mini, $0.75/$4.50 per 1M tokens):** Runs only on articles that pass Stage 1. Produces the full debate-framed card with mechanism chains, prop/opp arguments, weighing, and data points.

This typically filters out 40-60% of articles before they hit the expensive model, cutting monthly costs roughly in half.

---

#### Stage 1: Relevance Filter (GPT-5.4 Nano)

**Batching:** Batch 10-15 articles per API call. Nano handles this well.

**Model:** `gpt-5.4-nano`

**System prompt:**

```
You are a relevance filter for a competitive British Parliamentary (BP) debate research pipeline. Your job is to decide which news articles are worth deep analysis for debate prep.

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

Respond ONLY with a JSON array. No markdown, no preamble.
```

**User prompt:**

```
Filter these articles for debate relevance:

1. [Title] — [Source] — [URL]
[First 200 words of extracted text]

2. [Title] — [Source] — [URL]
[First 200 words of extracted text]

...
```

**API call parameters:**
- Model: `gpt-5.4-nano`
- Temperature: `0.1` (binary classification, keep it deterministic)
- Max tokens: `1000` per batch

**Post-processing:**
- Parse JSON array
- Keep only articles where `relevant: true`
- Carry forward `category` and `region` assignments to Stage 2

---

#### Stage 2: Full Analysis (GPT-5.4 Mini)

**Batching:** Process articles individually (not batched) for higher quality output per card.

**Model:** `gpt-5.4-mini`

**System prompt:**

```
You are a research assistant for a competitive British Parliamentary (BP) debater. Your job is to transform news articles into structured debate ammunition — the kind of material that wins extensions in closing half.

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

Respond ONLY with the JSON object. No markdown fences, no preamble.
```

**User prompt per article:**

```
Analyze this article for BP debate prep:

Title: {title}
Source: {source}
Published: {date}
URL: {url}
Pre-assigned category: {category}
Pre-assigned region: {region}

Full text:
{extracted_article_text}
```

**API call parameters:**
- Model: `gpt-5.4-mini`
- Temperature: `0.4` (specific enough for mechanisms, flexible enough for creative angles)
- Max tokens: `2000` per article

**Post-processing:**
- Parse JSON response, validate required fields exist
- If `"skip": true`, discard the article
- If JSON parsing fails, log the error and skip (don't crash the pipeline)
- Override `category` and `region` with Stage 2 values if they differ from Stage 1 (mini's judgment is better)

### 2.5 Card Output Format

Store as daily JSON files: `data/cards/YYYY-MM-DD.json`

```json
{
  "date": "2026-05-07",
  "last_updated": "2026-05-07T14:00:00Z",
  "cards": [
    {
      "id": "a1b2c3d4e5f6",
      "title": "EU Carbon Border Tax Forces ASEAN Into Retaliatory Tariff Bloc",
      "source": "Reuters",
      "url": "https://...",
      "published": "2026-05-07T12:30:00Z",
      "category": "Econ",
      "region": "EU / Southeast Asia",
      "background": "The EU's Carbon Border Adjustment Mechanism (CBAM), effective January 2026, imposes tariffs on imports based on their carbon footprint. ASEAN nations — responsible for ~$45B in annual EU-bound exports of steel, aluminum, and cement — announced a joint retaliatory framework at a special summit in Jakarta on May 5.",
      "prop_args": [
        {
          "thesis": "Unilateral carbon tariffs are the only mechanism that forces global decarbonization without requiring multilateral consensus.",
          "mechanisms": [
            "First, multilateral climate agreements have structurally failed to produce binding commitments. This is because (1) free-rider incentives mean nations benefit from others' emissions cuts without reducing their own, (2) enforcement mechanisms in agreements like Paris are toothless — there are no penalties for missing targets, (3) consensus requirements give veto power to petrostate holdouts like Saudi Arabia",
            "Second, CBAM creates a direct financial incentive to decarbonize. Three reasons this works where regulation doesn't: one, it targets the supply chain — manufacturers face cost pressure regardless of domestic regulation; two, the price signal is immediate and calculable, unlike speculative future carbon taxes; three, it's self-enforcing through customs infrastructure that already exists",
            "Third, the retaliatory response actually proves the mechanism works. If ASEAN nations form trade blocs in response, they must either (1) develop their own carbon pricing to gain CBAM exemptions, or (2) deepen trade dependency on other high-emitting nations, which is economically suboptimal. Both outcomes accelerate the global carbon pricing conversation."
          ]
        }
      ],
      "opp_args": [
        {
          "thesis": "CBAM is industrial protectionism laundered through climate language, and it disproportionately harms developing economies.",
          "mechanisms": [
            "First, the mechanism structurally disadvantages nations that industrialized later. This is because (1) developed nations built their wealth through carbon-intensive industrialization without bearing these costs, creating a historical inequity, (2) developing nations lack the capital to rapidly decarbonize production — clean steel requires ~$50-100/ton premium that eliminates their comparative advantage, (3) CBAM effectively subsidizes EU producers by raising the cost floor for competitors",
            "Second, the retaliatory trade bloc response creates genuine economic harm. Two impacts: one, trade fragmentation raises consumer prices globally by disrupting efficient supply chains; two, ASEAN nations may pivot toward China as primary trade partner, strengthening Chinese geopolitical influence — the opposite of EU strategic interests"
          ]
        }
      ],
      "weighing": "The biggest delta is whether the urgency of climate action justifies unilateral economic coercion. Prop wins if you can prove multilateral alternatives are structurally impossible; Opp wins if you can show CBAM causes net harm to the nations least responsible for emissions.",
      "stock_connections": ["Dutch Disease", "Race to the Bottom", "Structural Adjustment", "Dependency Theory"],
      "motion_areas": [
        "THBT developed nations should be permitted to impose unilateral carbon tariffs",
        "THP a world where trade policy is subordinated to climate goals",
        "THBT ASEAN nations should form a unified trade bloc in response to Western protectionism"
      ],
      "data_points": [
        "$45B annual ASEAN exports to EU in CBAM-covered sectors",
        "Clean steel requires $50-100/ton premium over conventional",
        "Paris Agreement has no enforcement penalties for missed targets",
        "CBAM effective January 2026 covering steel, aluminum, cement, electricity"
      ]
    }
  ]
}
```

### 2.6 GitHub Actions Workflow

File: `.github/workflows/digest.yml`

```yaml
name: Debate Digest Pipeline
on:
  schedule:
    - cron: '0 */3 * * *'  # Every 3 hours
  workflow_dispatch: {}     # Manual trigger for testing

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install feedparser openai trafilatura
      - run: python scripts/pipeline.py
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      - run: |
          git config user.name "Debate Digest Bot"
          git config user.email "bot@debatedigest.dev"
          git add data/ state.json
          git diff --cached --quiet || git commit -m "digest: $(date -u +%Y-%m-%dT%H:%M)"
          git push
```

**Required secret:** `OPENAI_API_KEY` in repo settings.

### 2.7 Backfill Script

File: `scripts/backfill.py`

One-time script to seed the system with initial data. Run locally or via `workflow_dispatch`.

**Logic:**
1. Start with an empty state: `{"processed": {}}`
2. Fetch all RSS feeds (most feeds retain 1-2 weeks of entries)
3. Process ALL entries (everything is "dirty" since state is empty)
4. Group output cards by their **publish date** (not processing date) into the correct `data/cards/YYYY-MM-DD.json` files
5. Write final `state.json` with all processed hashes
6. Update `data/index.json` with all dates
7. Commit everything

**Usage:**
```bash
export OPENAI_API_KEY=sk-...
python scripts/backfill.py
```

**Rate limiting:** Process max 5 articles per minute to avoid OpenAI rate limits. Add 12-second delay between API calls. Estimated backfill time for ~100 articles: ~20 minutes.

**Cost estimate for backfill:** ~100 articles through nano filter (~$0.02) → ~50-60 surviving articles through mini (~$0.35). **Total: ~$0.40.**

### 2.8 Ongoing Cost Estimate

**Stage 1 (Nano filter):**
- Per run: ~15 articles × ~300 tokens input (200-word excerpt + prompt) + ~100 tokens output = ~6K tokens
- Cost per run: ~$0.001 (essentially free)

**Stage 2 (Mini analysis):**
- Per run: ~6-8 articles survive filtering (40-50% filter rate) × ~1500 input + ~1000 output = ~15K-20K tokens
- Cost per run: ~$0.04

**Monthly totals:**
- 8 runs/day × 30 days = 240 runs
- Nano: ~$0.25/month
- Mini: ~$9.60/month
- **Total: ~$10/month** (vs ~$14 without the nano filter)
- GitHub Actions: ~240 runs × 2-3 min = ~600 min/month (well within 2,000 free tier)

**Savings breakdown:** The nano filter costs almost nothing ($0.25/mo) but eliminates ~40-50% of articles from hitting the mini model, saving ~$4-5/month. As RSS feeds scale up, the savings grow proportionally.

---

## 3. Frontend (GitHub Pages)

### 3.1 Tech Stack

- **Framework:** React + Vite
- **Styling:** Tailwind CSS
- **Hosting:** GitHub Pages via `gh-pages` branch or `/docs` folder
- **Data loading:** Fetch `/data/cards/YYYY-MM-DD.json` at runtime (same origin, static files)
- **Matter file API calls:** Fetch to Railway endpoint

### 3.2 Pages & Layout

#### 3.2.1 Daily Digest (Home — `/`)

- **Header:** Date selector, total card count, category breakdown badges (IR: 5, Econ: 3, Business: 4)
- **Filter bar:** Filter by category (IR / Econ / Business), region, text search across all card fields
- **Card grid:** Responsive — 2-col desktop, 1-col mobile
- **Navigation:** ← Previous Day | Today | Next Day →
- **Auto-refresh indicator:** If cards were last updated < 3h ago, show "Updated 45m ago" badge

#### 3.2.2 Individual Card Design

Each card has a **collapsed state** (default) and **expanded state**.

**Collapsed card:**
```
┌────────────────────────────────────────────────────────────┐
│ [IR]  EU / Southeast Asia                    Reuters · 2h │
│                                                            │
│ EU Carbon Border Tax Forces ASEAN Into                     │
│ Retaliatory Tariff Bloc                                    │
│                                                            │
│ The EU's CBAM, effective January 2026, imposes tariffs     │
│ on imports based on carbon footprint. ASEAN nations        │
│ announced a joint retaliatory framework at a Jakarta       │
│ summit on May 5.                                           │
│                                                            │
│ Stock: Dutch Disease · Race to the Bottom · 2 more         │
│                                                            │
│ [Expand ▾]                     [+ Matter File] [🔗 Source] │
└────────────────────────────────────────────────────────────┘
```

**Expanded card (accordion sections):**
```
┌────────────────────────────────────────────────────────────┐
│ [IR]  EU / Southeast Asia                    Reuters · 2h │
│                                                            │
│ EU Carbon Border Tax Forces ASEAN Into                     │
│ Retaliatory Tariff Bloc                                    │
│                                                            │
│ [Background]                                               │
│ The EU's CBAM, effective January 2026...                   │
│                                                            │
│ [▸ Prop Arguments]  ← expandable                           │
│   Thesis: Unilateral carbon tariffs are the only...        │
│   1) First, multilateral climate agreements have...        │
│   2) Second, CBAM creates a direct financial...            │
│   3) Third, the retaliatory response actually...           │
│                                                            │
│ [▸ Opp Arguments]   ← expandable                           │
│   Thesis: CBAM is industrial protectionism...              │
│   1) First, the mechanism structurally...                  │
│   2) Second, the retaliatory trade bloc...                 │
│                                                            │
│ [▸ Weighing]        ← expandable, visually distinct        │
│   The biggest delta is whether the urgency...              │
│                                                            │
│ [▸ Motion Areas]    ← expandable                           │
│   • THBT developed nations should be permitted to...       │
│   • THP a world where trade policy is...                   │
│                                                            │
│ [▸ Data Points]     ← expandable                           │
│   • $45B annual ASEAN exports to EU in CBAM sectors        │
│   • Clean steel requires $50-100/ton premium               │
│                                                            │
│ Stock: Dutch Disease · Race to the Bottom ·                │
│        Structural Adjustment · Dependency Theory           │
│                                                            │
│ [Collapse ▴]                   [+ Matter File] [🔗 Source] │
└────────────────────────────────────────────────────────────┘
```

**Key design decisions:**
- Background is always visible (not in accordion)
- Prop/Opp arguments are the core — accordion defaults to collapsed but users will open these most. Consider a "expand all" toggle.
- Weighing section should have a visually distinct treatment (accent left-border or highlight background) — this is the analytical money shot
- Stock connections shown as small inline tags/pills at bottom of card
- Mechanisms within prop/opp should render with numbered formatting preserving the "First, ... because (1)... (2)..." structure
- "Add to Matter File" button: calls Railway API, shows success toast, changes to "✓ In Matter File"

#### 3.2.3 Matter File Page (`/matter-file`)

- **Saved cards displayed fully expanded** — no accordion, the point is quick reference
- Cards grouped by category (IR → Econ → Business), each with a section header
- **Per-card actions:** Remove from matter file, add personal notes (text field saved to Railway)
- **Export button:** Downloads `.md` file from Railway `/export` endpoint
- **Search/filter** within saved cards

#### 3.2.4 Archive Page (`/archive`)

- Calendar or date-list with card counts per day
- Click date → loads that day's digest
- Shows category breakdown per day

### 3.3 Data Loading

The frontend loads card data from JSON files committed to the repo:

```javascript
const today = new Date().toISOString().split('T')[0];
const response = await fetch(`/data/cards/${today}.json`);
const { cards } = await response.json();
```

Maintain `data/index.json` listing all available dates (updated by pipeline each run):
```json
{
  "dates": ["2026-05-07", "2026-05-06", "2026-05-05"],
  "total_cards": 142,
  "last_updated": "2026-05-07T14:00:00Z"
}
```

---

## 4. Matter File API (Railway)

### 4.1 Tech Stack

- **Framework:** FastAPI (Python)
- **Database:** SQLite (single file, no external DB needed)
- **Deployment:** Railway ($5/mo hobby plan)

### 4.2 Data Model

```sql
CREATE TABLE matter_entries (
    id TEXT PRIMARY KEY,           -- same as card id
    card_data JSON NOT NULL,       -- full card JSON blob
    notes TEXT DEFAULT '',         -- user-added annotations
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4.3 API Endpoints

**Base URL:** `https://<app-name>.up.railway.app/api`

| Method | Endpoint                | Body / Params                  | Description                        |
|--------|-------------------------|--------------------------------|------------------------------------|
| GET    | `/matter-file`          | `?category=IR&search=tariff`   | List all saved entries (filterable)|
| POST   | `/matter-file`          | `{ card_data: {...} }`         | Add a card                         |
| DELETE | `/matter-file/{id}`     | —                              | Remove a card                      |
| PATCH  | `/matter-file/{id}`     | `{ notes: "..." }`            | Update notes on a saved card       |
| GET    | `/matter-file/export`   | `?format=md`                   | Export as formatted Markdown       |
| GET    | `/matter-file/check`    | `?ids=abc123,def456`           | Batch check which IDs are saved (for UI button state) |

**CORS:** Allow the GitHub Pages origin.

**Auth:** For v1, no auth — the Railway URL is effectively a secret. If this becomes multi-user, add a simple bearer token. Flag for v2.

### 4.4 Markdown Export Format

The `/matter-file/export` endpoint returns a `.md` file structured to match the CUSID matter file conventions observed in the uploaded reference files:

```markdown
# Debate Matter File
Generated: May 7, 2026

---

## International Relations

### EU Carbon Border Tax Forces ASEAN Into Retaliatory Tariff Bloc
*Reuters · May 7, 2026*

**Background:**
The EU's Carbon Border Adjustment Mechanism (CBAM), effective January 2026,
imposes tariffs on imports based on their carbon footprint. ASEAN nations —
responsible for ~$45B in annual EU-bound exports — announced a joint retaliatory
framework at a special summit in Jakarta on May 5.

**Proposition:**

*Thesis: Unilateral carbon tariffs are the only mechanism that forces global
decarbonization without requiring multilateral consensus.*

1) First, multilateral climate agreements have structurally failed to produce
   binding commitments. This is because (1) free-rider incentives mean nations
   benefit from others' emissions cuts without reducing their own, (2) enforcement
   mechanisms in agreements like Paris are toothless — there are no penalties for
   missing targets, (3) consensus requirements give veto power to petrostate
   holdouts like Saudi Arabia

2) Second, CBAM creates a direct financial incentive to decarbonize. Three
   reasons this works where regulation doesn't: one, it targets the supply
   chain — manufacturers face cost pressure regardless of domestic regulation;
   two, the price signal is immediate and calculable; three, it's self-enforcing
   through customs infrastructure that already exists

3) Third, the retaliatory response actually proves the mechanism works...

**Opposition:**

*Thesis: CBAM is industrial protectionism laundered through climate language,
and it disproportionately harms developing economies.*

1) First, the mechanism structurally disadvantages nations that industrialized
   later...

2) Second, the retaliatory trade bloc response creates genuine economic harm...

**Weighing:**
The biggest delta is whether the urgency of climate action justifies unilateral
economic coercion...

**Useful data points:**
- $45B annual ASEAN exports to EU in CBAM-covered sectors
- Clean steel requires $50-100/ton premium over conventional
- Paris Agreement has no enforcement penalties

**Stock arguments:** Dutch Disease, Race to the Bottom, Structural Adjustment,
Dependency Theory

**Potential motions:**
- THBT developed nations should be permitted to impose unilateral carbon tariffs
- THP a world where trade policy is subordinated to climate goals

**Personal notes:** [user's notes if any]

---

### [Next IR entry...]

---

## Economics

### [Econ entries...]

---

## Business

### [Business entries...]
```

**Key formatting rules for export:**
- Group by category with H2 headers (## International Relations, ## Economics, ## Business)
- Each card is H3 (### Title)
- Arguments use numbered lists matching the matter file convention: `1) First, ... because (1)... (2)... (3)...`
- Indentation preserves the nested mechanism structure
- Data points as bullet lists
- Stock connections as inline comma-separated list
- Personal notes appended at end of each entry if present
- This format should be directly printable and usable as a tournament matter file

---

## 5. Repo Structure

```
debate-digest/
├── .github/
│   └── workflows/
│       └── digest.yml              # GitHub Actions cron workflow
├── scripts/
│   ├── pipeline.py                 # Main pipeline: fetch → dedupe → extract → process → commit
│   ├── backfill.py                 # One-time backfill script
│   ├── feeds.py                    # RSS feed definitions, fetcher, validation
│   ├── extractor.py                # trafilatura article extraction + fallback chain
│   ├── processor.py                # Two-stage LLM: nano filter → mini analysis
│   └── utils.py                    # Hashing, date utils, state.json management
├── api/                            # Railway API (separate deployable service)
│   ├── main.py                     # FastAPI app with CORS
│   ├── database.py                 # SQLite init, connection, queries
│   ├── models.py                   # Pydantic models for request/response
│   ├── export.py                   # Markdown export logic matching matter file format
│   ├── requirements.txt            # fastapi, uvicorn, aiosqlite
│   └── Procfile                    # web: uvicorn main:app --host 0.0.0.0 --port $PORT
├── frontend/                       # React + Vite (builds to gh-pages or /docs)
│   ├── src/
│   │   ├── App.jsx                 # Router setup
│   │   ├── pages/
│   │   │   ├── Digest.jsx          # Daily card grid with filters
│   │   │   ├── MatterFile.jsx      # Saved cards view with export
│   │   │   └── Archive.jsx         # Historical date browser
│   │   ├── components/
│   │   │   ├── Card.jsx            # Card with collapsed/expanded states
│   │   │   ├── ArgumentBlock.jsx   # Renders prop/opp with numbered mechanisms
│   │   │   ├── FilterBar.jsx       # Category/region/search filters
│   │   │   ├── StockTag.jsx        # Pill/badge for stock argument connections
│   │   │   └── Toast.jsx           # Success/error notifications
│   │   └── lib/
│   │       ├── api.js              # Railway matter file API client
│   │       ├── cards.js            # Static card data loader from JSON files
│   │       └── constants.js        # Category colors, stock argument list
│   ├── public/
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── package.json
├── data/                           # Auto-generated by pipeline
│   ├── cards/                      # Daily JSON files
│   │   ├── 2026-05-07.json
│   │   └── ...
│   └── index.json                  # Date listing
├── state.json                      # Processed article hashes (auto-generated)
└── README.md
```

---

## 6. Implementation Order

### Phase 0: Backfill + Pipeline Validation (do this first)

1. Set up repo structure with empty scaffolding
2. Implement `feeds.py` — validate all RSS feed URLs, drop dead ones, find replacements via RSSHub
3. Implement `extractor.py` — trafilatura extraction with fallback chain
4. Implement `utils.py` — hashing, state.json read/write, date helpers
5. Implement `processor.py` — two-stage pipeline: nano relevance filter (batched) → mini full analysis (individual). JSON parsing and error handling for both stages.
6. Implement `pipeline.py` — orchestrate the full flow
7. Implement `backfill.py` — run pipeline with empty state, group cards by publish date
8. **Run backfill locally** to seed initial data. Verify output quality.
9. Manually review 5-10 generated cards against the matter file style. Iterate on the prompt if mechanisms are too shallow or generic.

### Phase 1: GitHub Actions Automation
1. Create `.github/workflows/digest.yml`
2. Add `OPENAI_API_KEY` to repo secrets
3. Push and verify the cron runs successfully
4. Monitor first few runs for errors

### Phase 2: Frontend
1. Scaffold React + Vite app in `frontend/`
2. Build `Card.jsx` — collapsed/expanded states, accordion sections, argument block rendering
3. Build `ArgumentBlock.jsx` — renders prop/opp with numbered mechanisms, preserving the nesting
4. Build `Digest.jsx` — loads today's cards, renders grid, day navigation
5. Build `FilterBar.jsx` — category, region, text search
6. Build `Archive.jsx` — date picker / list with card counts
7. Configure Vite to build to GitHub Pages-compatible output
8. Deploy to GitHub Pages
9. **Read `/mnt/skills/public/frontend-design/SKILL.md` before writing any frontend code** — follow its design guidelines for typography, color, and spatial composition

### Phase 3: Matter File API
1. Set up FastAPI app in `api/`
2. Implement SQLite schema and CRUD operations
3. Implement `/check` endpoint for batch ID lookups
4. Implement `/export` endpoint with Markdown formatting matching Section 4.4
5. Deploy to Railway
6. Wire up frontend "Add to Matter File" button → Railway API
7. Build `MatterFile.jsx` — saved cards list, remove, notes, export download

### Phase 4: Polish
1. Error handling throughout (failed feeds, OpenAI errors, network issues)
2. Loading states, empty states, error states in frontend
3. Mobile responsiveness pass
4. `README.md` with setup instructions, architecture overview, cost estimates
5. Edge case: handle days with zero new cards gracefully

---

## 7. Configuration & Secrets

| Secret/Config        | Where               | Value                              |
|----------------------|----------------------|------------------------------------|
| `OPENAI_API_KEY`     | GitHub repo secrets  | OpenAI API key                     |
| `RAILWAY_API_URL`    | Frontend `.env`      | `https://<app>.up.railway.app/api` |
| Cron schedule        | `digest.yml`         | `0 */3 * * *` (every 3 hours)      |
| GitHub Pages source  | Repo settings        | `gh-pages` branch or `/docs`       |

---

## 8. Stock Arguments Reference

The LLM prompt references stock arguments. Here is the canonical list — the frontend should recognize these for consistent tag styling:

**Economic:** Dutch Disease, Moral Hazard, Race to the Bottom, Structural Adjustment, Resource Curse, Dependency Theory, Brain Drain, Capital Flight, Rent-Seeking, Infant Industry, Comparative Advantage, Austerity

**Political:** Democratic Backsliding, Authoritarian Resilience, Mandate Theory, Slippery Slope (legal/policy), Regulatory Capture, Balkanization, Self-Determination, Humanitarian Intervention

**Social:** Chilling Effect, Moral Hazard (behavioral), Perverse Incentives, Tragedy of the Commons, Cultural Imperialism, Tokenism, Paternalism

---

## 9. Design Direction (Frontend)

Aesthetic: **Newsroom wire × debate prep tool.** Informationally dense but scannable. Think Bloomberg Terminal legibility meets clean modern card UI.

- **Dark mode default** (debaters prep late at night)
- **Monospace or semi-mono for data fields** (mechanisms, data points) — authoritative feel
- **Clean sans-serif for titles and summaries**
- **Category color system:** IR = slate blue, Econ = emerald, Business = amber — consistent pill badges
- **Weighing section:** visually distinct with accent left-border or subtle highlight
- **Stock argument pills:** small, muted tags at card bottom
- **Dense but scannable:** collapsed cards show enough to decide whether to expand. Background + stock tags + category should be enough signal.

---

## 10. Future Considerations (v2)

- **Auth:** Simple bearer token for Railway API when sharing with debate team
- **Push notifications:** Browser notifications on new card batches
- **Quality scoring:** Additional LLM pass to rate debate relevance 0-10, surface only cards above threshold (beyond the current nano binary filter)
- **RPi migration:** Move cron from GitHub Actions to RPi if usage limits tighten
- **Matter file annotations:** Rich text notes, highlight system, tagging
- **Mobile PWA:** ServiceWorker + cached cards for offline tournament use
- **Team features:** Shared matter files, collaborative annotations
- **Custom sources:** User-configurable RSS feed list via frontend settings
