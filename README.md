# RADAR

Competitive intelligence tool for VCs. Paste a startup URL → get a structured competitive memo in under 60 seconds.

Built for the **Linkup hackathon** — ship > perfect.

---

## What it does

```
URL startup
    ↓
[PHASE 1 — UNDERSTAND] ~15s
  Linkup /search + /fetch Crunchbase → CompanyProfile
    ↓
[PHASE 2 — DISCOVER] ~20s
  Linkup /search deep → 15 competitors deduplicated by website
    ↓
[PHASE 3 — ENRICH] ~60s
  Linkup /tasks batch + /fetch pricing → CompetitorProfile × 15 + PricingSignals
    ↓
JSON → Claude extraction → React frontend
```

---

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.11+, FastAPI, Pydantic v2 |
| LLM extraction | `claude-sonnet-4-20250514` |
| Search | Linkup API |
| Frontend | React 18, Tailwind, TypeScript, Vite |
| Map | Leaflet (react-leaflet) |
| Geocoding | Nominatim (OSM) |
| Deploy | Vercel (frontend) + Railway/Render (backend) |

No SQL DB, no Redis, no Docker. JSON file cache, async everywhere.

---

## Project layout

```
RADAR/
├── AGENTS.md                     ← agent communication rules
├── STATUS.yaml                   ← single source of truth, current state
├── CLAUDE/CLAUDE.md              ← full architecture & conventions
├── docs/
│   ├── design-system/            ← 12 markdown specs (Palantir × Perplexity, dark only)
│   ├── learning/
│   └── smoke-report/
└── radar/
    ├── BACKLOG.md                ← NOW/NEXT/LATER
    ├── JOURNAL.md                ← daily log
    ├── backend/
    │   ├── main.py               ← FastAPI + CORS + rate limit + kill switch + cache
    │   ├── pipeline/             ← understand.py / discover.py / enrich.py
    │   ├── clients/              ← linkup_client.py / claude_client.py
    │   ├── models/               ← Pydantic v2 (DataPoint pattern)
    │   ├── utils/                ← geocoding (Nominatim), cache, dedup
    │   └── evals/                ← Braintrust evals per phase + bench
    ├── frontend/
    │   ├── src/components/       ← CompanyCard, CompetitorGrid, CompetitorMap, PricingSignalFeed
    │   ├── src/design-system/    ← tokens.ts + tailwind.preset.ts (source of truth)
    │   └── src/pages/index.tsx
    ├── cache/                    ← gitignored JSON cache
    └── scripts/
```

---

## Setup

### Backend

```bash
cd RADAR/radar/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# .env (do NOT commit)
# LINKUP_API_KEY=...
# ANTHROPIC_API_KEY=...
# NOMINATIM_USER_AGENT=radar-hackathon

uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd RADAR/radar/frontend
npm install
npm run dev   # port 3000
```

`frontend/.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Run a pipeline phase (CLI)

```bash
cd RADAR/radar/backend
source .venv/bin/activate

python -m pipeline.understand "doctolib.fr"
python -m pipeline.discover "doctolib.fr"
python -m pipeline.enrich '["livi.fr", "qare.fr", "medadom.com"]'
```

## Evals

```bash
braintrust eval evals/eval_understand.py
braintrust eval evals/eval_discover.py
braintrust eval evals/eval_enrich.py
```

---

## Current state

See [`RADAR/STATUS.yaml`](RADAR/STATUS.yaml) for the live snapshot — health, components, bench results, gaps, next milestones.

Latest bench (4 domains, target total <90s):

| Domain | Understand | Discover | Enrich | Total |
|---|---:|---:|---:|---:|
| linear.app | 12.0s | 107.2s | 17.4s | 136.5s |
| pennylane.com | 11.0s | 78.0s | 21.6s | 110.6s |
| mistral.ai | 45.0s | 132.1s | 16.5s | 193.6s |
| cal.com | 9.7s | 59.4s | 22.7s | 91.7s |

**Known bottleneck:** Phase 2 (discover) runs 5× slower than target. Investigating Linkup `/tasks` batch vs sequential calls.

---

## Demo cache (pre-computed)

Five companies must be in cache before live demo: Doctolib, Notion, Slite, Alan, Pennylane. See `STATUS.yaml > pre_cache_demo`.

---

## Documentation

- Architecture & conventions → [`RADAR/CLAUDE/CLAUDE.md`](RADAR/CLAUDE/CLAUDE.md)
- Design system specs → [`RADAR/docs/design-system/`](RADAR/docs/design-system/)
- Design tokens (code) → [`RADAR/radar/frontend/src/design-system/tokens.ts`](RADAR/radar/frontend/src/design-system/tokens.ts)
- Backlog → [`RADAR/radar/BACKLOG.md`](RADAR/radar/BACKLOG.md)
- Journal → [`RADAR/radar/JOURNAL.md`](RADAR/radar/JOURNAL.md)

---

## Notes

- Linkup never returns GPS coordinates — always resolve `city + country` via Nominatim (1 req/s rate limit).
- Every Pydantic field sourced from Linkup/Claude uses the `DataPoint` pattern: `value + confidence + source_url + extracted_at`.
- Dark mode only, no toggle. Mono (JetBrains) for data, sans (Inter) for prose.
- Cost: ~€0.60 per full pipeline run on Linkup. Use `tests/fixtures/` mocks for debugging loops.
