# RADAR — Deploy Runbook

## Architecture

```
[Demo viewer browser]
        |
        v
[Vercel: frontend-prototype-opal.vercel.app]   ← static HTML/JSX/CSS
        |
        | fetch(window.RADAR_API + "/scan/...")
        v
[ngrok tunnel: https://xxxx.ngrok.io]          ← public URL
        |
        v
[Local Mac: uvicorn main:app on :8000]         ← FastAPI backend
```

Frontend = static deploy on Vercel (no build step, plain HTML + JSX via Babel CDN).
Backend = runs on your Mac, exposed publicly via ngrok during demo.

## Vercel project

- Team: `paul-pietras-projects`
- Project: `frontend-prototype`
- Production URL: https://frontend-prototype-opal.vercel.app
- Inspect: https://vercel.com/paul-pietras-projects/frontend-prototype
- Linked to local path: `RADAR/radar/frontend-prototype/.vercel/`

## One-time setup

### Backend (Mac)

Make sure `.env` in `RADAR/radar/backend/` has:
```
LINKUP_API_KEY=lp-...
ANTHROPIC_API_KEY=sk-ant-...
NOMINATIM_USER_AGENT=radar-hackathon
SUPABASE_URL=...                  # optional but recommended for cache
SUPABASE_SERVICE_KEY=...
FRONTEND_URL=https://frontend-prototype-opal.vercel.app
```

### ngrok

```bash
brew install ngrok
ngrok config add-authtoken <token-from-ngrok.com>
```

## Deploy frontend (after code changes)

From repo root:

```bash
cd RADAR/radar/frontend-prototype
export PATH="/Users/paul.pietra/.npm-global/bin:$PATH"
vercel deploy --prod --yes
```

Deploy takes ~20s. URL stays the same: `frontend-prototype-opal.vercel.app`.

## Update backend URL (after ngrok URL change)

The ngrok URL changes each time ngrok restarts (unless you pay $8/mo for a fixed domain).

Two ways to swap:

### Option 1 — Edit + redeploy (recommended for demo day)

1. Get current ngrok URL (e.g. `https://abc123.ngrok-free.app`)
2. Edit `RADAR/radar/frontend-prototype/index.html` line 32:
   ```html
   window.RADAR_API = "https://abc123.ngrok-free.app";
   ```
3. Redeploy: `vercel deploy --prod --yes`

### Option 2 — Quick test via browser console

For one-off tests without redeploy, open the Vercel URL, hit F12 console:
```javascript
window.RADAR_API = "https://abc123.ngrok-free.app";
location.reload();
```
(Won't persist on refresh — only for quick checks.)

## Demo day runbook (5 min prep)

```bash
# Terminal 1: backend
cd RADAR/radar/backend
source .venv/bin/activate
uvicorn main:app --reload
# wait for "Uvicorn running on http://0.0.0.0:8000"

# Terminal 2: ngrok tunnel
ngrok http 8000
# copy the https://*.ngrok-free.app URL

# Terminal 3: update + redeploy frontend with new URL
cd RADAR/radar/frontend-prototype
# edit index.html line 32 with the new ngrok URL
vercel deploy --prod --yes
# wait ~20s

# Test in browser
open https://frontend-prototype-opal.vercel.app
# trigger a scan, confirm pipeline runs through ngrok → local backend
```

## CORS

Backend must allow the Vercel origin. Check `RADAR/radar/backend/main.py` CORS middleware includes:
- `https://frontend-prototype-opal.vercel.app`
- `https://*.vercel.app` (covers preview deploys)
- `http://localhost:8000` (local dev)

If `FRONTEND_URL` env var is set, the backend should pick it up automatically (verify in `main.py`).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Page loads but blank | JSX parse error in browser | Open F12 console, fix the .jsx file, redeploy |
| `Failed to fetch` on /scan | ngrok URL stale or CORS reject | Re-check URL in index.html, check backend CORS |
| ngrok returns "Tunnel not found" | tunnel died | Restart `ngrok http 8000` |
| Vercel deploy 403 | team Vercel auth enabled | Disable in Vercel dashboard → Settings → Deployment Protection |

## Vercel MCP tools (in Claude Code)

Already wired. Useful prompts:
- "list my Vercel deployments for frontend-prototype"
- "show me the runtime logs for the latest deploy"
- "get the latest deploy URL"
