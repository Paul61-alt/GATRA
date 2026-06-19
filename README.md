# RADAR

**Competitive intelligence for VCs.** Paste a startup URL → get a structured competitive memo (company profile, ranked competitors, pricing signals, positioning maps) in under 60 seconds.

Winner of the **Linkup hackathon** (May 2026). Now open source.

```
URL startup
    ↓  [UNDERSTAND ~15s]  Linkup search + Crunchbase fetch → CompanyProfile
    ↓  [DISCOVER  ~20s]   Linkup deep search → ~15 competitors (deduped by website)
    ↓  [ENRICH    ~60s]   Linkup batch + pricing fetch → CompetitorProfile × N + signals
    ↓  Claude extraction → React frontend (Overview · Map · Pricing · Timeline · Positioning)
```

## Repository layout

The app lives under [`RADAR/`](RADAR/):

```
RADAR/
├── radar/backend/          ← FastAPI + Pydantic pipeline (Python 3.11+)
├── radar/frontend-prototype/  ← build-free React 18 (CDN + Babel), static deploy
├── docs/                   ← architecture, deploy runbook, design system
├── CLAUDE/CLAUDE.md        ← engineering conventions
└── README.md              ← full setup, usage, and architecture
```

## Quickstart

Full instructions (env vars, run, evals): **[`RADAR/README.md`](RADAR/README.md)**.

```bash
# Backend
cd RADAR/radar/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then fill in your keys
uvicorn main:app --reload --port 8000

# Frontend (no build step — just a static server)
cd RADAR/radar/frontend-prototype
python3 -m http.server 8080     # open http://localhost:8080
```

> 💸 **Cost note:** the `/scan*` endpoints call paid APIs. A full run is ~€0.60; a 15-item batch can hit ~€4.50. The backend ships with daily budget caps (see `.env.example`) and a fail-closed auth gate. Use `backend/tests/fixtures/` mocks for debugging loops.

## Documentation

- Setup & usage → [`RADAR/README.md`](RADAR/README.md)
- Architecture (non-technical) → [`RADAR/docs/Learning/ARCHITECTURE.md`](RADAR/docs/Learning/ARCHITECTURE.md)
- Engineering conventions → [`RADAR/CLAUDE/CLAUDE.md`](RADAR/CLAUDE/CLAUDE.md)
- Contributing → [`RADAR/CONTRIBUTING.md`](RADAR/CONTRIBUTING.md)
- Deploy runbook → [`RADAR/docs/DEPLOY_RUNBOOK.md`](RADAR/docs/DEPLOY_RUNBOOK.md)

## Security

- All secrets come from environment variables — never commit `.env` (it is gitignored).
- `/scan*` endpoints are gated by a shared bearer token (`RADAR_SHARED_TOKEN`); the API fails closed if it is unset.
- Testers can supply their own Linkup key via the `X-Linkup-Key` header (BYOK).

## License

[MIT](LICENSE) — free to use, modify, and distribute; keep the copyright notice.

## Credits

Built by **Paul Pietra** (backend & pipeline) and cofounder (frontend & design). Powered by [Linkup](https://linkup.so) and [Anthropic Claude](https://www.anthropic.com).
