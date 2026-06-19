# RADAR — Deploy Runbook

## Architecture

```
[Tester browser]
        |
        v
[Vercel: frontend-prototype-opal.vercel.app]   ← static HTML/JSX/CSS + PasswordGate
        |
        | fetch(window.RADAR_API + "/scan/...")
        | Authorization: Bearer <RADAR_SHARED_TOKEN>
        v
[Render: radar-backend-je6o.onrender.com]      ← FastAPI, always-on (sleeps 15min idle)
        |
        v
[Linkup + Anthropic + Supabase]                ← external APIs (rate + budget capped)
```

- Frontend = static deploy on Vercel (no build step, plain HTML + JSX via Babel CDN). Single PasswordGate React component wraps `<App/>`, stores bearer token in `localStorage` (`radar:token`), and `window.fetch` is monkey-patched to auto-attach the token on every call to `window.RADAR_API`.
- Backend = FastAPI on Render free tier. Auth via `Authorization: Bearer <RADAR_SHARED_TOKEN>` on all `/scan*`, `/scans*`, `/analyze`. `/health` stays open for Render health probes.
- Cost cap = `_check_daily_budget_eur` in `main.py` uses `linkup_client.estimate_today_cost_eur()` reading the JSONL ledger. Refuses 429 when today's spend > `RADAR_DAILY_BUDGET_EUR`.

## Live services

| Service | URL | Dashboard |
|---|---|---|
| Frontend | https://frontend-prototype-opal.vercel.app | https://vercel.com/paul-pietras-projects/frontend-prototype |
| Backend | https://radar-backend-je6o.onrender.com | https://dashboard.render.com → `radar-backend` |
| Repo | https://github.com/Paul61-alt/GATRA | Branch watched by Render: `feat/render-deploy` |

## Shared access token

Token in use: stored in Render env var `RADAR_SHARED_TOKEN`. Rotate via Render dashboard → Environment → edit → Save → triggers redeploy.

Share with testers via Slack/email, NOT in the public URL.

To rotate: `openssl rand -hex 24` → paste new value in Render → save → wait ~1 min for redeploy.

## Demo day prep (zero manual work — already live)

Open https://frontend-prototype-opal.vercel.app. Password gate asks for token. Enter it. Use the app.

If Render service has been idle >15 min, the first request triggers a cold start (~30s wait). The app already shows a loading state for scans, so testers see "scanning…" rather than a frozen page. To avoid this entirely, ping `/health` once before sharing the link.

## Common operations

### Update frontend code

```bash
git checkout feat/render-deploy
# edit files in radar/frontend-prototype/
git commit -am "fix(frontend): ..."
git push origin feat/render-deploy
# then trigger Vercel redeploy:
cd radar/frontend-prototype
export PATH="/Users/paul.pietra/.npm-global/bin:$PATH"
vercel deploy --prod --yes
```

Vercel does NOT auto-deploy on push (not connected to GitHub). CLI deploy = explicit.

### Update backend code

```bash
git checkout feat/render-deploy
# edit files in radar/backend/
git commit -am "fix(backend): ..."
git push origin feat/render-deploy
```

Render auto-deploys on push to `feat/render-deploy` (Auto-Deploy: On Commit). Watch progress in Render dashboard. Health check at `/health` must return 200 within ~10 min or deploy is marked failed.

### Update env vars on Render

Render dashboard → `radar-backend` → Environment tab → edit → Save changes. Render redeploys automatically.

### Lower cost cap urgently (kill switch)

Two options:

1. **Soft kill (refuse 429)**: Render → Environment → set `RADAR_DAILY_BUDGET_EUR=0` → save. Any `/scan` returns 429 immediately.
2. **Hard kill (refuse 503)**: Render → Environment → set `RADAR_KILL_SWITCH=1` → save. Any `/scan` returns 503 "Service temporarily disabled".

Both trigger an auto-redeploy of ~1 min.

### Rotate shared token

Render → Environment → `RADAR_SHARED_TOKEN` → paste new value (generate with `openssl rand -hex 24`) → save → testers must re-enter the new token on the Vercel page.

## CORS

Backend CORS allows:
- `https://frontend-prototype-opal.vercel.app` (prod)
- `https://*.vercel.app` (preview deploys, via `allow_origin_regex`)
- `http://localhost:3000`, `:5173`, `:8080` (local dev)
- Plus whatever `FRONTEND_URL` env var holds

If you add a custom domain, update `FRONTEND_URL` in Render and redeploy.

## Local dev (working on the code)

```bash
# Backend
cd radar/backend
source .venv/bin/activate
# leave RADAR_REQUIRE_AUTH unset (or =0) so /scan works without a token in local
uvicorn main:app --reload

# Frontend — edit radar/frontend-prototype/index.html:
#   window.RADAR_API = "http://localhost:8000"
# Serve any way (file:// works, or python3 -m http.server 8080)
```

For local with auth enabled (matching prod behavior):
```bash
RADAR_SHARED_TOKEN=dev123 RADAR_REQUIRE_AUTH=1 uvicorn main:app --reload
# Then in browser console:
window.radarSetToken("dev123"); location.reload();
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| 401 "Missing bearer token" | Frontend didn't send token | Clear `localStorage` + re-enter token in PasswordGate |
| 401 "Invalid token" | Token in browser ≠ Render env var | Rotate Render token + ask user to re-enter |
| 429 `daily_budget_reached` | Hit EUR cost cap | Raise `RADAR_DAILY_BUDGET_EUR` on Render OR wait until tomorrow (UTC day boundary) |
| 503 "Service temporarily disabled" | `RADAR_KILL_SWITCH=1` is set | Remove from Render env vars |
| 60s wait then `/scan` errors | Render cold start | Ping `/health` first to wake the dyno |
| CORS error in browser console | Origin not whitelisted | Add origin to `_ALLOWED_ORIGINS` in `main.py` or update `FRONTEND_URL` env |
| Page loads, blank | JSX parse error | F12 console → find the failing `.jsx` file → fix → redeploy |
| Vercel deploy 403 | Vercel team auth on | Vercel dashboard → Settings → Deployment Protection → off |

## Vercel MCP tools (in Claude Code)

Already wired. Useful prompts inside Claude Code:
- "list my Vercel deployments for frontend-prototype"
- "show me the runtime logs for the latest deploy"
- "get the latest deploy URL"
