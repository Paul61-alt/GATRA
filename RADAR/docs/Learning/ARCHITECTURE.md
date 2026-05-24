# Radar — Architecture

> Une URL en entrée → 3 phases Python → interface React avec l'analyse concurrentielle.

---

## Pipeline en un coup d'œil

```
URL saisie
    │
    ▼
[POST /scan ou /scan/stream]
    │
    ├─── cache hit ? (radar_{domain}_{YYYY-MM-DD}.json)
    │       └─→ retour immédiat, 0 appel Linkup, dashboard direct
    │
    ▼
Phase 1 — UNDERSTAND (~10-45s)
    │  1 appel Linkup /search → profil complet du sujet
    ▼
Phase 2 — DISCOVER (~60-130s)
    │  1 appel Linkup /search deep → 15 concurrents directs
    ▼
Phase 3 — ENRICH (~2-5 min, dépend de MAX_ENRICH)
    │  N × Linkup /research (1 par concurrent) en parallèle via asyncio.gather
    │  Polling SSE : progress events toutes les ~7s pendant le wait
    ▼
Phase 4 — TRANSFORM (~0s)
    │  Mise en forme pour le frontend
    ▼
RadarOutput → cache écrit → React affiche l'analyse
```

---

## Phase par phase

### Phase 1 — UNDERSTAND
`pipeline/understand.py`

| | |
|---|---|
| **Ce qu'il fait** | Construit le profil complet de l'entreprise cible |
| **Endpoint Linkup** | `POST /v1/search` |
| **Paramètres** | `depth=standard` · `outputType=structured` · schéma JSON 30 champs |
| **Input** | domaine (ex: `linear.app`) |
| **Output** | `CompanyProfile` — nom, HQ + coordonnées GPS, funding, marchés, signaux de croissance |
| **Durée** | ~10-45s |
| **Appels Linkup** | 1 |
| **Coût** | ~€0.055 (search structured) |

---

### Phase 2 — DISCOVER
`pipeline/discover.py`

| | |
|---|---|
| **Ce qu'il fait** | Trouve 15 concurrents directs avec contexte + scoring threat |
| **Endpoint Linkup** | `POST /v1/search` |
| **Paramètres** | `depth=deep` (jusqu'à 10 itérations, scrape multi-URL) · `outputType=structured` |
| **Input** | `CompanyProfile` du sujet (nom, positionnement, marchés) |
| **Output** | Liste de 15 `dict` — nom, site, HQ, funding stage, one-liner, différenciateur, threat_score |
| **Durée** | ~60-130s ← **goulot principal** |
| **Appels Linkup** | 1 (Linkup fait jusqu'à 10 sous-requêtes en interne) |
| **Coût** | ~€0.055 (search structured deep) + petit appel Claude pour scorer threat |

---

### Phase 3 — ENRICH
`pipeline/enrich.py`

| | |
|---|---|
| **Ce qu'il fait** | Profil concurrent approfondi via Linkup Research per concurrent |
| **Endpoint Linkup** | `POST /v1/research` (1 job par concurrent) · puis `GET /v1/research/{id}` pour polling |
| **Paramètres** | `mode=Investigate` · `depth=S` (override possible) · `outputType=structured` + schema JSON |
| **Contenu** | Pricing tiers exacts, signaux LinkedIn fondateurs, funding complet, signaux produit typés, faiblesses |
| **Input** | Les 15 concurrents de Discover (slicés à `MAX_ENRICH`) |
| **Output** | N `CompetitorProfile` — pricing structuré, LinkedIn URL + posts fondateurs, signals typés |
| **Cap concurrents** | `RADAR_MAX_ENRICH` env var (default 5, dev recommandé 1) |
| **Parallélisme** | `asyncio.gather` sur N jobs simultanés (chaque job = 1 research + polling) |
| **Polling** | `GET /v1/research/{id}` toutes les ~7s via `wait_for_research(on_poll=...)` |
| **SSE progress** | callback `on_poll` émet `{phase: "ENRICH", status: "polling", competitor, elapsed, job_id}` toutes les 7s → frontend voit avancement |
| **Durée** | ~2-5 min par job (Linkup traite en background) |
| **Coût** | **€1.50 flat** par research, quel que soit le depth (S/M/L/XL) → MAX_ENRICH × €1.50 |

⚠️ **Attention coût** : avec MAX_ENRICH=5 (default), un scan = 5 × €1.50 = **€7.50** → bloqué par `DAILY_HARD_CAP_EUR=5` au runtime. En dev, exporter `RADAR_MAX_ENRICH=1` → €1.50/scan.

---

### Phase 4 — TRANSFORM
`pipeline/transform.py`

| | |
|---|---|
| **Ce qu'il fait** | Convertit les données pipeline au format attendu par le frontend |
| **Endpoint Linkup** | Aucun |
| **Input** | `PipelineRun` (CompanyProfile + N CompetitorProfile) |
| **Output** | `RadarOutput` (camelCase JSON) → écrit dans cache `radar_{domain}_{date}.json` |
| **Durée** | ~0s |
| **⚠ Placeholders** | `similarity=0.5`, `threat="medium"`, `features=[]`, `radar.scores=[50…]`, `pricingTiers=[]` (Phase 5 future avec Claude) |

---

## Endpoints Linkup utilisés

| Endpoint | Où | Ce qu'il fait | Latence | Coût/appel |
|---|---|---|---|---|
| `POST /v1/search` · `depth=standard` | UNDERSTAND, fallback | 1 recherche + extraction structurée JSON | ~10-45s | €0.006 (sourcedAnswer) / €0.055 (structured) |
| `POST /v1/search` · `depth=deep` | DISCOVER | Jusqu'à 10 itérations, scrape multi-URL | ~60-130s | €0.055 |
| `POST /v1/research` | ENRICH | Agent autonome, rapport multi-sources structuré | 2-5 min | **€1.50 flat** (tous depth confondus) |
| `GET /v1/research/{id}` | ENRICH polling | Status check (free, exempté du budget counter) | — | €0 |
| `POST /v1/fetch` | Optionnel | Charge une URL spécifique → markdown | ~1s | €0.005 |
| `POST /v1/tasks` | **Non utilisé** | Batch endpoint legacy — abandonné au profit de `/research` direct | — | — |

---

## Clients et utilitaires

| Fichier | Rôle |
|---|---|
| `clients/linkup_client.py` | Wrapper HTTP Linkup — retry, budget quotidien, ledger, toutes les méthodes |
| `clients/claude_client.py` | Wrapper Anthropic — threat scoring (DISCOVER), VC memo (e2e script) |
| `utils/geocoding.py` | Nominatim (OpenStreetMap) — lat/lng depuis ville+pays, 1 req/s max |
| `utils/cache.py` | Cache fichier JSON par domaine+date — évite de re-appeler Linkup |
| `utils/dedup.py` | Normalise les domaines et dédoublonne les concurrents |

---

## Budget & Guards (linkup_client.py)

Système de protection contre l'explosion de coûts Linkup.

| Garde-fou | Valeur | Effet |
|---|---|---|
| `DAILY_HARD_CAP_EUR` | **€5.0** | `BudgetExceededError` levé si `cumul + estimated_cost > cap` avant appel |
| `DAILY_WARN_CAP_EUR` | €3.0 | Warning log quand on s'approche |
| `RADAR_DAILY_BUDGET` env | default 50 | Compteur d'appels journalier (counts /search + /fetch + /research, exempte les polls GET) |
| `RADAR_MAX_ENRICH` env | default 5 | Slice `competitors[:N]` avant Phase 3 → limite N × €1.50 |
| `RADAR_KILL_SWITCH` env | `1`/`true` | Bloque tout appel Linkup (kill switch d'urgence) |
| Ledger | `cache/linkup_usage.jsonl` | 1 ligne par appel : `{ts, date, endpoint, status, cost_eur}` |
| `estimate_today_cost_eur()` | — | Somme du `cost_eur` ledger pour aujourd'hui (ok-status only) |

**Worst case avec defaults actuels** : MAX_ENRICH=5 → 5×€1.50 = €7.50 → bloqué par cap €5 avant le 4ᵉ research.
**En dev (MAX_ENRICH=1)** : 1 scan = €1.50 + ~€0.11 (understand + discover) ≈ **€1.61/scan**.

---

## Cache flow (court-circuit du pipeline)

- **Clé** : `radar_{domain}_{YYYY-MM-DD}` (UTC)
- **Storage** : `RADAR/radar/cache/radar_{domain}_{date}.json`
- **Lecture** : `main.py:207` (`/scan/stream`) et `main.py:154` (`/scan`) read cache AVANT de lancer le pipeline
- **Écriture** : `main.py:248` (stream) et `main.py:183` (scan) après transform OK
- **Invalidation** : naturelle par date (J+1 → cache miss → re-scan)

**Implication démo** : pré-cacher les boîtes démo le jour J = 0 risque budget, 0 latence, animation skip.
Pour forcer l'animation : supprimer le fichier cache OU utiliser un domaine non encore caché.

---

## Modèles de données

```
CompanyProfile      ← sujet (understand.py)
CompetitorProfile   ← chaque concurrent (enrich.py)
PipelineRun         ← enveloppe : id + status + les deux ci-dessus
    ↓ transform.py
RadarOutput         ← format exact du frontend (camelCase JSON)
    ↓ cache write
radar_{domain}_{date}.json   ← lu par /scan + /scan/stream
```

⚠️ Les types TypeScript dans `frontend/src/types/` sont des mirrors manuels — sync à la main si modèles Pydantic changent.

---

## Ce qui manque — Phase 5 (Synthesize)

Ces champs sont des placeholders dans `transform.py`. Claude les calculera dans une phase future.

| Champ frontend | Valeur actuelle | Ce que Claude fera |
|---|---|---|
| `similarity` | `0.5` fixe | Comparer les profils → score 0-1 |
| `threat` | `"medium"` fixe | Croiser funding + similarity → high/med/low |
| `features[]` | `[]` | Générer la liste de features à comparer |
| `capabilities{}` | `{}` | Évaluer chaque concurrent sur chaque feature |
| `radar.scores` | `[50, 50, 50, 50, 50, 50]` | Noter sur 6 axes produit (0-100) |
| `pricingTiers` | `[]` | Parser le texte brut Linkup → tiers structurés |
| `arr`, `customers` | `null` | Estimer depuis les signaux publics |

---

## Pour lancer le pipeline

```bash
# Serveur complet (dev = MAX_ENRICH=1 pour limiter le coût)
cd RADAR/radar/backend
source .venv/bin/activate
RADAR_MAX_ENRICH=1 uvicorn main:app --reload --port 8000

# E2E rapide (1 concurrent, 1 research, +VC memo) — script CLI
python evals/eval_e2e_simple.py linear.app

# Tester une phase isolée
python -m pipeline.understand linear.app
python -m pipeline.enrich '[{"name":"Notion","website":"notion.so"}]'

# POC Research endpoint (Linkup beta)
python -m evals.poc_research notion.so --depth M
```

---

## Annexe — Recovery pattern

Si une recherche est interrompue côté backend (refresh frontend → SSE cut → `pipeline_task.cancel()`), le job Linkup `/research/{id}` continue côté serveur Linkup. L'argent est déjà dépensé. Pour le récupérer sans re-lancer un research :

`evals/recover_indy.py` (exemple concret) :
1. Hardcoder le `JOB_ID` (loggé au moment de la soumission)
2. `linkup.wait_for_research(JOB_ID, max_wait=900)` → récupère l'output une fois ready
3. Re-courir understand + discover (€~0.11) pour reconstituer le contexte autour
4. `_parse_result()` → CompetitorProfile
5. `cache_set("radar_{domain}", radar_output)` → frontend hit cache pour €0

Coût total recovery : €~0.11 au lieu de €1.61. À refaire si interruption pendant ENRICH.
