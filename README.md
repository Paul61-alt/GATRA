# RADAR

**Competitive intelligence for VCs.** Paste a startup URL → get a structured competitive memo (company profile, ranked competitors, pricing signals, positioning maps) in under 60 seconds.

Winner of the **Linkup hackathon** (May 2026). Now open source.

> The repo is named `GATRA` (team handle); the product is **RADAR**.

---

## Demo

- **Live app:** https://frontend-prototype-opal.vercel.app (password-gated — ask for the access token)
- **Backend API:** https://radar-backend-je6o.onrender.com

**New scan** — paste a product URL, get a ranked competitive map in ~60s:

![Radar — new scan](RADAR/docs/screenshots/scan_page.png)

**Your analyses** — every URL you've scanned, ranked by recency:

![Radar — analyses history](RADAR/docs/screenshots/homepage.png)

---

## What it does

```
URL startup
    ↓
[PHASE 1 — UNDERSTAND] ~15s
  Linkup /search + /fetch Crunchbase → CompanyProfile
    ↓
[PHASE 2 — DISCOVER] ~20s
  Linkup /search deep → ~15 competitors, deduplicated by website
    ↓
[PHASE 3 — ENRICH] ~60s
  Linkup /tasks batch + /fetch pricing → CompetitorProfile × N + PricingSignals
    ↓
JSON → Claude extraction → React frontend (Overview, Map, Pricing, Timeline, Positioning)
```

---

## Repository layout

The app lives under [`RADAR/`](RADAR/):

```
RADAR/
├── radar/backend/             ← FastAPI + Pydantic pipeline (Python 3.11+)
├── radar/frontend-prototype/  ← build-free React 18 (CDN + Babel), static deploy
├── docs/                      ← architecture, deploy runbook, design system
├── CLAUDE/CLAUDE.md           ← engineering conventions
└── CONTRIBUTING.md            ← contribution rules
```

---

## Prerequisites

- **Python 3.11+** (backend)
- A modern browser + any static file server (frontend is build-free)
- API keys:
  - **`LINKUP_API_KEY`** — search/fetch engine ([linkup.so](https://linkup.so))
  - **`ANTHROPIC_API_KEY`** — Claude extraction (model `claude-sonnet-4-20250514`)
  - **`NOMINATIM_USER_AGENT`** — required by OpenStreetMap geocoding ToS
- Optional:
  - **`BRAINTRUST_API_KEY`** — only if you run evals
  - **`SUPABASE_URL` + `SUPABASE_SERVICE_KEY`** — persistence; falls back to local JSON cache if absent

> 💸 **Cost note:** a full pipeline run costs ~€0.60 on Linkup (a 15-item batch scan can hit ~€4.50). Never loop a real pipeline to debug — the unit tests stub the Claude client (`RADAR/radar/backend/tests/test_memo.py`), so they run with no network and no API spend.

---

## Installation

### Backend

```bash
cd RADAR/radar/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `RADAR/radar/backend/.env` (never commit it — see `.env.example`):

```bash
LINKUP_API_KEY=lp-xxxxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
NOMINATIM_USER_AGENT=radar-hackathon
# optional
BRAINTRUST_API_KEY=xxxxxxxx
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...service-role-key...
```

### Frontend

No build step. It's plain HTML + `.jsx` transpiled in-browser by Babel standalone, with React loaded from CDN. You only need a static server.

```bash
cd RADAR/radar/frontend-prototype
python3 -m http.server 8080
```

Then open http://localhost:8080.

Point the frontend at your local backend by editing `window.RADAR_API` in [`RADAR/radar/frontend-prototype/index.html`](RADAR/radar/frontend-prototype/index.html):

```js
window.RADAR_API = "http://localhost:8000";
```

---

## Usage

### Run the API

```bash
cd RADAR/radar/backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

The `/scan*` endpoints are gated by a Bearer token (shared secret). Health check stays open:

```bash
curl http://localhost:8000/health
```

Key endpoints: `POST /scan` (full run), `POST /scan/stream` (SSE progress), `GET /scan/status/{run_id}` (resume after refresh), `GET /scans` (history).

### Run a single pipeline phase from the CLI

```bash
cd RADAR/radar/backend
source .venv/bin/activate

python -m pipeline.understand "doctolib.fr"
python -m pipeline.discover "doctolib.fr"
python -m pipeline.enrich '["livi.fr", "qare.fr", "medadom.com"]'
```

### Evals (optional, requires Braintrust)

```bash
braintrust eval evals/eval_understand.py
braintrust eval evals/eval_discover.py
braintrust eval evals/eval_enrich.py
```

### Clear the cache

```bash
rm -rf RADAR/radar/cache/*.json
```

---

## Architecture (short)

- **Backend** — Python 3.11+, FastAPI, Pydantic v2. No SQL DB, no Redis, no Docker. Async everywhere (`httpx.AsyncClient`). Local JSON file cache keyed by `{domain}_{YYYY-MM-DD}`, optional Supabase persistence.
- **Search** — Linkup API (`/search`, `/fetch`, `/tasks`). GPS coords come from Nominatim (OSM), never from Linkup.
- **Extraction** — Claude (`claude-sonnet-4-20250514`) turns raw search results into typed `DataPoint`s (`value + confidence + source_url + extracted_at`).
- **Frontend** — build-free React 18 prototype (CDN + Babel standalone), dark-mode only, deployed as static files on Vercel.
- **Deploy** — Vercel (frontend) + Render (backend). `/health` must stay rate-limit-exempt or Render restarts kill in-flight scans.

Full conventions and pipeline detail: [`RADAR/CLAUDE/CLAUDE.md`](RADAR/CLAUDE/CLAUDE.md). Architecture (non-technical): [`RADAR/docs/Learning/ARCHITECTURE.md`](RADAR/docs/Learning/ARCHITECTURE.md). Design system: [`RADAR/docs/design-system/`](RADAR/docs/design-system/). Deploy runbook: [`RADAR/docs/DEPLOY_RUNBOOK.md`](RADAR/docs/DEPLOY_RUNBOOK.md).

---

## Security

- All secrets come from environment variables — never commit `.env` (it is gitignored).
- `/scan*` endpoints are gated by a shared bearer token (`RADAR_SHARED_TOKEN`); the API fails closed if it is unset.
- Testers can supply their own Linkup key via the `X-Linkup-Key` header (BYOK).

---

## Contribution

See [`RADAR/CONTRIBUTING.md`](RADAR/CONTRIBUTING.md) for the full rules. In short:

- **Branches:** `feature/`, `fix/`, `chore/`, `docs/` (e.g. `fix/similarity-scores`)
- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/) — `type(scope): short description`
- **Never push to `main`** directly — open a PR.
- If you change a Pydantic model, update the matching frontend data shape in the same PR.
- If you change pipeline phases, Linkup endpoints, models, or budget guards, update [`RADAR/docs/Learning/ARCHITECTURE.md`](RADAR/docs/Learning/ARCHITECTURE.md) in the same task.

Current state, bench results, and next milestones live in [`RADAR/STATUS.yaml`](RADAR/STATUS.yaml).

---

## License

Released under the [MIT License](LICENSE). Free to use, modify, and distribute — keep the copyright notice.

---

## Contact & credits

- **Paul Pietra** — backend & pipeline
- **Mathieu Gaillarde** — frontend & design

Built for the Linkup hackathon (May 2026). Powered by [Linkup](https://linkup.so) and [Anthropic Claude](https://www.anthropic.com).
