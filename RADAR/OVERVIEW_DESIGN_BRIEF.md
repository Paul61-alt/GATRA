# Understand → Overview · Design Recommendations

> **Mode:** design brief, **NO implementation**. Recommendations only, backed by Mobbin patterns + the makipeople cache schema.

---

## Context

The Understand → Overview screen is the executive landing for a scan. Cache (`understand_makipeople.com.json`, 415 lines) carries ~30 distinct fields with confidence + source per atomic value, but the prototype (`screens-overview.jsx`, 569 lines) renders only ~30% of that signal. The screen also mixes subject context with competitive data (Top threats, Analyst summary), which duplicates downstream screens.

Goal: re-architect Overview around **what's unique to the subject**, surface the rich data already cached, and bake in the trust signals (confidence, source, freshness) that make this a research tool rather than a dashboard.

---

## Data audit — cache vs. current render

| Field | In cache | On screen now |
|---|---|---|
| `name`, `domain`, `summary` | ✅ | ✅ (summary used as tagline) |
| `founded_year`, `hq`, `geo_coverage` | ✅ | partial (founded ✅, hq ✅, geo ❌) |
| `employees.value` + confidence + source + evidence | ✅ | value only |
| `employee_growth_yoy` | ✅ (null for makipeople) | ✅ if present |
| `funding.total_raised_eur` (+ confidence/source) | ✅ | total only |
| `funding.last_round`, `last_round_date` | ✅ | ✅ |
| `funding.rounds[]` (Seed, Series A with lead/date/amount) | ✅ | ❌ **missed** |
| `funding_stage` | ✅ | ❌ |
| `equity_story` (narrative) | ✅ | ❌ |
| `acquisition` (acquired, acquirer, year) | ✅ | ❌ |
| `arr_usd`, `customer_count` | partial | ✅ |
| `positioning` (one-liner moat) | ✅ | ❌ **missed** |
| `markets[]`, `target_segment`, `target_verticals[]` | ✅ | ❌ |
| `business_model`, `gtm_motion`, `pricing_model` (+ each w/ conf/source) | ✅ | ❌ |
| `pricing.tiers[]`, `pricing.free_plan`, `recent_changes` | schema present | ❌ |
| `key_differentiator` (single sentence, sourced) | ✅ | ❌ **missed** |
| `top_3_features[]` | ✅ | ❌ **missed** |
| `tech_stack[]` | ✅ | ❌ |
| `notable_customers[]` (name, domain, segment, industry, evidence) | ✅ | name+logo+segment only — `industry` + `evidence` unused |
| `notable_investors[]` | ✅ | ✅ |
| `key_people[]` (full list w/ background) | ✅ | filtered to co-founders only; `background` + non-founders dropped |
| `growth_signals[]` (bullets) | ✅ (5 entries) | ❌ **missed** |
| `recent_news[]` (date, headline, source_url) | ✅ (5 entries) | ❌ **missed** |
| `source_urls[]` (~80 URLs global) | ✅ | ❌ |
| `pipeline_run_id`, `analysis_version` | ✅ | ❌ (trust/debug surface) |

**Biggest losses:** `positioning`, `key_differentiator`, `top_3_features`, `growth_signals`, `recent_news`, `funding.rounds[]`. These are the qualitative high-value signals — exactly what differentiates RADAR from a Crunchbase listing.

---

## Mobbin pattern library — what to lean on

| Pattern | Source | Apply to |
|---|---|---|
| Sticky right-rail metadata (locations, size, total raised, markets) | Wellfound (Notion profile) | Replace single stat row with persistent identity rail |
| Stacked round cards w/ amount + round + date + valuation + press link | Wellfound (Notion Funding) | `funding.rounds[]` timeline |
| Insight strip — "Score · News · Tech · Funding · Job postings · Employee trends" tabs | Apollo (Google company view) | Top-of-page chip strip, anchor links to sections |
| KV attribute panel — Industry tags, Foundation date, Estimated ARR, etc. | Attio (record detail) | At-a-glance facts bar |
| Dedup'd news with `N sources` badge per headline | Fey (Tesla news) | `recent_news[]` collapse (Series A story has 5 duplicate entries) |
| "Healthy · last evaluated 13 min ago" freshness chip | Databricks data quality | Trust banner under hero |
| Citation chip → tooltip with evidence + source URL | Profound, Elicit | Hover any value with `confidence/source_url/evidence` |
| Inline source pill `[1]` linking to global sources list | Perplexity-style (cross-ref) | `source_urls[]` index |

---

## Proposed layout — 6 zones

```
┌───────────────────────────────────────────────────────────────────────────┐
│ ZONE A · HERO RIBBON                                                       │
│  [logo] Maki People  makipeople.com↗  [SUBJECT]                            │
│  "AI hiring intelligence platform with autonomous agents for…"  ← positioning
│  📍 Paris · 🌐 Global · founded 2021 · 🕐 scanned 2h ago [⟳ rescan]         │
└───────────────────────────────────────────────────────────────────────────┘
┌───────────────────────────────────────────────────────────────────────────┐
│ ZONE B · AT-A-GLANCE BAR  (6 micro-cells, confidence-dot per cell)         │
│  Employees ● Stage ● Total raised ● Business model ● GTM ● Target segment  │
│   122          Series A    €33.8M       B2B          Sales-led  Grand Cpte │
└───────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────┬─────────────────────────────────────┐
│ ZONE C · THE MOAT  (NEW)            │ ZONE D · NEWS & MOMENTUM            │
│  Key differentiator  (1 sentence)   │  Recent news (deduped, sourced)     │
│  ─────────────────────────────────  │  ─ Jan 15 · Series A — 5 sources    │
│  Top 3 features  (bullets)          │  ─ Jan 16 · founderlodge…           │
│  ─ AI screening / E2E / bias mit.   │  ─────────────────────────────────  │
│  ─────────────────────────────────  │  Growth signals (bullets)           │
│  Tech stack  (chip cloud)           │  ─ Series A €27.8M Jan 2025         │
│                                     │  ─ Hiring 60+ roles                 │
│                                     │  ─ CEO relocating to NYC            │
└─────────────────────────────────────┴─────────────────────────────────────┘
┌───────────────────────────────────────────────────────────────────────────┐
│ ZONE E · FUNDING TIMELINE  (full-width)                                    │
│   Total €33.8M raised over 2 rounds · Stage: Series A                      │
│   ─────────────────────────────────────                                    │
│   [A] €27.8M · Series A · Jan 2025 · led by Blossom Capital   [press↗]     │
│   [S] €6.0M  · Seed     · Dec 2021 · — Frst Capital, GFC, Kima, +50 BA      │
│   ─────────────────────────────────────                                    │
│   equity_story (one paragraph, narrative)                                  │
└───────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────┬─────────────────────────────────────┐
│ ZONE F · TEAM (unified, filterable) │ ZONE G · FOOTPRINT                  │
│  [Founders] [Execs] [All]           │  Customers (logo strip, by segment) │
│  ─ Maxime Legardez · CEO ↗          │  Investors (logo strip)             │
│  ─ Benjamin Chino  · CPO ↗          │  Verticals (chip cloud)             │
│  ─ Paul Louis Caylar · COO ↗        │  Geo coverage (Global / regions)    │
│  ─ Marc Desazars   · GTM ↗          │                                     │
│  hover → background paragraph       │                                     │
└─────────────────────────────────────┴─────────────────────────────────────┘
```

### Cuts from current Overview
- **Top threats** card → moves to a Competitive tab (already redundant with Positioning + Search/Discover screens).
- **Analyst summary** card → either becomes a one-line summary in the hero ribbon, or moves to Competitive tab. Don't keep on Overview.
- The split co-founders / notable_investors / notable_customers as three separate "card per row" entities → consolidate into **Zone G Footprint** so the visual hierarchy is clearer.

---

## New atomic patterns to introduce

### 1. Confidence dot + citation tooltip
Every value with `{value, confidence, source_url, evidence, extracted_at}` gets a tiny coloured dot to its right:
- ● green = high · ● amber = medium · ○ grey = low
- Hover reveals: evidence snippet, source URL (clickable), relative timestamp ("extracted 2h ago").
- Pattern lifted from Databricks data-quality monitor + Elicit screening pills.

### 2. News dedupe with `N sources` badge
`recent_news[]` currently has 5 entries — all 5 are the same Series A story from different outlets. Group by canonical headline, show the badge `5 sources` with a popover listing each outlet + date. Pattern: Fey financial news.

### 3. At-a-glance KV bar
Replace the current 4-stat card with a 6-cell horizontal strip. Each cell = `LABEL ● VALUE`, confidence dot inline, no big serif numbers. Visual model: Apollo "Company overview" sidebar.

### 4. Stacked funding round cards
Each round = a small card with: round letter chip (S, A, B…), amount, date, lead investor, press link. Vertical stack. Pattern: Wellfound Notion funding.

### 5. Unified Team card with filter chips
Instead of "Co-founders only" hardcoded, single card with chips `[Founders] [Execs] [All]`. Each person row: avatar, name, role, LinkedIn link, background paragraph behind a "▸ expand". Pattern: Peerlist team grouping.

### 6. Tech stack chip cloud
`tech_stack[]` rendered as Attio-style outlined chips. Optional secondary chip cloud for `target_verticals[]`.

### 7. Freshness ribbon
Below hero: small chip `🕐 Scanned 2h ago · Pipeline 3f21038e · Analysis v4.0 [⟳ rescan]`. Pattern: Databricks "Healthy as of X" + observability tools.

---

## Visual treatment notes

- **Keep** existing design tokens: warm-stone bg, terracotta accent, Roboto/Slab/Mono trio. They're a strong identity — don't break.
- **Add** confidence palette: `--confidence-high: var(--positive)`, `--confidence-medium: #d4a64a`, `--confidence-low: var(--fg-4)`.
- **Add** subtle citation chip style — small mono `[1]` outlined, hover-only underline.
- **Density**: ZoneB at-a-glance bar should respect `[data-density]` token (compact = single row of 6, comfortable = 2 rows of 3).
- Don't introduce a chart library beyond Chart.js (already used in Positioning). Funding timeline is type-only, no graph.

---

## Critical files (read-only references for future implementation)

- [RADAR/radar/frontend-prototype/screens-overview.jsx](RADAR/radar/frontend-prototype/screens-overview.jsx) — current Overview component (lines 27–353)
- [RADAR/radar/frontend-prototype/data.js](RADAR/radar/frontend-prototype/data.js) — the data shape passed to OverviewScreen
- [RADAR/radar/backend/pipeline/transform.py](RADAR/radar/backend/pipeline/transform.py) — maps cache JSON → frontend data shape (will need to expose more fields)
- [RADAR/radar/cache/understand_makipeople.com.json](RADAR/radar/cache/understand_makipeople.com.json) — reference cache used in this brief

---

## Suggested next step

Pick the 2–3 zones you want to prototype first. My recommendation, in priority order:

1. **Zone C (The Moat)** — highest signal-to-cost; surfaces `positioning` + `key_differentiator` + `top_3_features` + `tech_stack`. These are the fields that justify the scan vs. a Google search.
2. **Zone D-news (dedup'd recent_news)** — visible momentum; one of the most polished patterns to copy from Fey.
3. **Zone E (funding timeline)** — replaces a single number with a story; uses the Wellfound pattern directly.

Then iterate Zone B (at-a-glance bar + confidence dots) as the trust foundation across the screen.

---

## Verification (when later implemented)

- Load `understand_makipeople.com.json` → every zone renders without "—" placeholders for fields present in cache.
- Hover any confidence dot → tooltip shows the matching `evidence` + clickable `source_url`.
- Group `recent_news[]` → 4 distinct headline cards (the Series A story collapses 5 → 1 with `5 sources` badge).
- Funding timeline → 2 round cards, total at top matches `funding.total_raised_eur.value`.
- Resize to compact density → at-a-glance bar collapses to 2 rows.
