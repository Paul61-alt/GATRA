# Task: Copier plan Supabase dans docs

**Action:** Copier contenu vers `/Users/paul.pietra/Dev/GATRA/docs/SUPABASE_PERSISTENCE.md`  
**Source:** `/Users/paul.pietra/.claude/plans/actuellement-nous-sommes-en-fluffy-llama.md`  
**Nommage:** cohérent avec `docs/Learning/ARCHITECTURE.md`

---

# Plan: Supabase comme couche de persistance RADAR

## Context

Actuellement, RADAR utilise un cache fichier (`radar_{domain}_{date}.json`) géré par `utils/cache.py`. C'est simple mais limité: pas d'historique cross-session, pas de multi-user, pas de dashboard usage. L'objectif est d'ajouter Supabase comme backend de persistance **sans casser l'existant** — approche additive, file cache reste en fallback.

---

## Réponse à la question lead dev

**Est-ce rapide avec MCP ?** Oui. ~1h si projet Supabase existe déjà, ~1h30 si creation from scratch.

**Approche lead dev :** additive, pas de big bang. On n'enlève pas le file cache. On ajoute Supabase comme couche primaire. Si env vars absentes → fallback file (système actuel intact). Un seul fichier change vraiment : `utils/cache.py`.

---

## Schema Supabase (2 tables)

```sql
-- Remplace radar_{domain}_{date}.json
CREATE TABLE scans (
  id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  domain      TEXT NOT NULL,
  scanned_date DATE NOT NULL DEFAULT CURRENT_DATE,
  result_json JSONB NOT NULL,
  duration_ms INTEGER,
  created_at  TIMESTAMPTZ DEFAULT now(),
  UNIQUE(domain, scanned_date)
);

-- Remplace cache/linkup_usage.jsonl
CREATE TABLE usage_events (
  id         UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  ts         TIMESTAMPTZ NOT NULL,
  endpoint   TEXT,
  status     TEXT,
  cost_eur   FLOAT,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

---

## Fichiers modifiés

| Fichier | Changement |
|---------|-----------|
| `radar/backend/utils/cache.py` | Ajouter Supabase client, modifier get/set/invalidate pour essayer Supabase d'abord, file fallback |
| `radar/backend/requirements.txt` | Ajouter `supabase` |
| `.env` (ou `.env.local`) | Ajouter `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` |

**Tout le reste inchangé** — `main.py`, pipeline, models : rien à toucher.

---

## Implémentation cache.py

```python
# Logique principale
def get(domain: str) -> Optional[dict]:
    # 1. Try Supabase
    if _sb():
        row = _sb().table("scans").select("result_json") \
            .eq("domain", domain).eq("scanned_date", str(date.today())) \
            .maybe_single().execute()
        if row.data:
            return row.data["result_json"]
    # 2. Fallback file cache (comportement actuel)
    p = _path(domain)
    if p.exists():
        return json.loads(p.read_text())
    return None

def set(domain: str, data: dict) -> None:
    # 1. Write Supabase
    if _sb():
        _sb().table("scans").upsert({
            "domain": domain,
            "scanned_date": str(date.today()),
            "result_json": data,
            "duration_ms": data.get("query", {}).get("durationMs"),
        }).execute()
    # 2. Always write file (belt + suspenders)
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _path(domain).write_text(json.dumps(data, ensure_ascii=False, indent=2))
```

`_sb()` retourne client Supabase ou None si env vars absentes.

---

## Runbook — déroulement exact (ordre strict)

### STEP 0 — Pré-requis (30 sec)
Avoir sous la main :
- `SUPABASE_URL` (format: `https://xxxx.supabase.co`)
- `SUPABASE_SERVICE_ROLE_KEY` (pas anon key — service role pour bypass RLS)

Si pas de projet → MCP `mcp__supabase__get_project_url` pour vérifier si déjà connecté.

---

### STEP 1 — Créer les tables via MCP (1 min)

Appeler `mcp__supabase__apply_migration` avec name=`add_scans_and_usage` et query:

```sql
CREATE TABLE IF NOT EXISTS scans (
  id           UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  domain       TEXT NOT NULL,
  scanned_date DATE NOT NULL DEFAULT CURRENT_DATE,
  result_json  JSONB NOT NULL,
  duration_ms  INTEGER,
  created_at   TIMESTAMPTZ DEFAULT now(),
  UNIQUE(domain, scanned_date)
);

CREATE TABLE IF NOT EXISTS usage_events (
  id         UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  ts         TIMESTAMPTZ NOT NULL,
  endpoint   TEXT,
  status     TEXT,
  cost_eur   FLOAT,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

Vérifier avec `mcp__supabase__list_tables` → doit voir `scans` + `usage_events`.

---

### STEP 2 — Ajouter dépendance Python (30 sec)

Dans `radar/backend/requirements.txt` (ou équivalent) :
```
supabase>=2.0.0
```

Puis :
```bash
pip install supabase
```

---

### STEP 3 — Ajouter env vars (30 sec)

Dans `radar/backend/.env` (ou `.env` racine) :
```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...  # service role key
```

---

### STEP 4 — Réécrire `utils/cache.py` (10 min)

Remplacer entièrement [radar/backend/utils/cache.py](radar/backend/utils/cache.py) :

```python
import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).parent.parent.parent / "cache"

# ── Supabase client (lazy, None si env vars absentes) ──────────────────────
_sb_client = None

def _sb():
    global _sb_client
    if _sb_client is not None:
        return _sb_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        _sb_client = create_client(url, key)
        logger.info("Supabase client initialized")
    except Exception as e:
        logger.warning("Supabase init failed, file-only mode: %s", e)
        _sb_client = None
    return _sb_client


# ── File cache helpers (inchangés) ─────────────────────────────────────────
def _key(domain: str) -> str:
    return f"{domain.lower().replace('/', '_')}_{date.today().isoformat()}"

def _path(domain: str) -> Path:
    return _CACHE_DIR / f"{_key(domain)}.json"


# ── Public API ──────────────────────────────────────────────────────────────
def get(domain: str) -> Optional[dict]:
    # 1. Supabase (primary)
    if _sb():
        try:
            row = _sb().table("scans").select("result_json") \
                .eq("domain", domain.lower()) \
                .eq("scanned_date", str(date.today())) \
                .maybe_single().execute()
            if row.data:
                logger.info("supabase cache hit domain=%s", domain)
                return row.data["result_json"]
        except Exception as e:
            logger.warning("Supabase get failed, falling back to file: %s", e)

    # 2. File fallback
    p = _path(domain)
    if p.exists():
        logger.info("file cache hit domain=%s", domain)
        return json.loads(p.read_text())
    return None


def set(domain: str, data: dict) -> None:
    # 1. Supabase upsert
    if _sb():
        try:
            _sb().table("scans").upsert({
                "domain": domain.lower(),
                "scanned_date": str(date.today()),
                "result_json": data,
                "duration_ms": data.get("query", {}).get("durationMs"),
            }).execute()
            logger.info("supabase cache write domain=%s", domain)
        except Exception as e:
            logger.warning("Supabase set failed: %s", e)

    # 2. File (belt + suspenders — toujours)
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = _path(domain)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    logger.info("file cache write domain=%s path=%s", domain, p)


def invalidate(domain: str) -> None:
    # Supabase delete
    if _sb():
        try:
            _sb().table("scans") \
                .delete() \
                .eq("domain", domain.lower()) \
                .eq("scanned_date", str(date.today())) \
                .execute()
        except Exception as e:
            logger.warning("Supabase invalidate failed: %s", e)

    # File delete
    p = _path(domain)
    if p.exists():
        p.unlink()
        logger.info("cache invalidated domain=%s", domain)
```

---

### STEP 5 — Vérification (2 min)

```bash
# 1. Lancer scan (cache miss → pipeline complet)
curl -s -X POST http://localhost:8000/scan \
  -H "Content-Type: application/json" \
  -d '{"url":"linear.app"}' | jq .query.durationMs
# Attendu: 60000+ ms (pipeline ran)
```

Via MCP `mcp__supabase__execute_sql` :
```sql
SELECT domain, scanned_date, duration_ms, created_at 
FROM scans 
ORDER BY created_at DESC 
LIMIT 3;
```
Doit voir une ligne `linear.app`.

```bash
# 2. Re-scan → cache HIT Supabase
curl -s -X POST http://localhost:8000/scan \
  -H "Content-Type: application/json" \
  -d '{"url":"linear.app"}' | jq .query.durationMs
# Attendu: <500ms (cache hit)
```

---

## Risques

| Risque | Mitigation |
|--------|-----------|
| Supabase down | File cache fallback automatique |
| JSONB trop gros (>1MB) | RadarOutput ~50-100KB, OK |
| Supabase write fail → scan perdu | File cache écrit en // |
| RLS bloque les writes | Utiliser service role key (bypass RLS) |
