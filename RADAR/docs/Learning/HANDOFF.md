# RADAR — Document de passation

> **Pour qui ?** Ton collègue qui reprend le développement.
> **Projet :** Radar — veille concurrentielle VC. URL startup → mémo concurrentiel structuré en < 60s.
> **Démo :** 29 mai 2026 · **Freeze features (cut-line) :** 25 mai 2026

---

## En un coup d'œil — Le pipeline

```
URL saisie par l'utilisateur
        │
        ▼
  Cache hit ?  ──YES──▶  Réponse instantanée (€0, 0 appel API)
        │ NO
        ▼
Phase 1 — UNDERSTAND (~15s)
  Qui est cette boîte ? Funding, marchés, positionnement.
  → 1 appel Linkup /search · Coût ≈ €0.055
        │
        ▼
Phase 2 — DISCOVER (~60-130s) ← GOULOT ACTUEL
  Qui sont les 15 concurrents directs ?
  → 1 appel Linkup /search deep · Claude les trie par menace · Coût ≈ €0.055
        │
        ▼
Phase 3 — ENRICH (~20s)
  Pricing exact, signaux LinkedIn, faiblesses de chaque concurrent.
  → 1 appel Linkup /research (mode batched) · Coût ≈ €1.50 flat
        │
        ▼
Phase 4 — SYNTHESIZE (~0s)
  Score 0-100 sur 6 axes : Breadth · Depth · Global · Developer · Pricing · Trust
  → Aucun appel API, heuristiques pures · Coût = €0
        │
        ▼
Phase 5 — TRANSFORM (~0s)
  Mise en forme JSON camelCase pour le frontend React
        │
        ▼
  Cache écrit → Frontend affiche l'analyse
```

**Coût total par scan : ≈ €1.61**
**Coût démo (cache hit) : €0**

---

## Ce qu'on a livré cette session

### Nouveaux fichiers

| Fichier | Ce que ça fait |
|---------|----------------|
| [`pipeline/synthesize.py`](../../radar/backend/pipeline/synthesize.py) | **Phase 4 — Scoring radar.** Calcule les 6 scores (Breadth, Depth, Global, Developer, Pricing, Trust) pour chaque entité. Zéro appel LLM, heuristiques explicites. Avant : tous les scores étaient `[50,50,50,50,50,50]` en dur. |
| [`evals/eval_e2e_simple.py`](../../radar/backend/evals/eval_e2e_simple.py) | **Script E2E de validation.** Fait tourner les 4 phases sur 1 concurrent et génère un mémo VC. Coût ≈ €0.65. Utilisé pour pré-cacher les démos. |
| [`evals/recover_indy.py`](../../radar/backend/evals/recover_indy.py) | **Script de récupération d'urgence.** Si le frontend est rafraîchi pendant un scan (SSE coupé), le job Linkup continue côté serveur et est déjà facturé. Ce script récupère l'output sans repayer. Dépense : €0.11 au lieu de €1.61. |

### Fichiers modifiés — ce qui a changé

| Fichier | Avant | Après |
|---------|-------|-------|
| [`clients/linkup_client.py`](../../radar/backend/clients/linkup_client.py) | Pas de contrôle de budget | **Système de budget complet** : hard cap €5/jour, warn cap €3, ledger JSONL des appels, retry avec backoff exponentiel, kill switch d'urgence |
| [`pipeline/enrich.py`](../../radar/backend/pipeline/enrich.py) | 1 appel /research par concurrent (max 5) | **Mode batched** : 1 seul appel /research pour tous les concurrents (€1.50 flat). Mode legacy toujours dispo via env var. |
| [`pipeline/understand.py`](../../radar/backend/pipeline/understand.py) | Schema 12 champs | Schema 22 champs, callback de progression SSE |
| [`pipeline/discover.py`](../../radar/backend/pipeline/discover.py) | Liste brute de concurrents | + Scoring de menace via Claude (0-100), tri par score |
| [`pipeline/transform.py`](../../radar/backend/pipeline/transform.py) | Scores radar `[50,50,50,50,50,50]` hardcodés | Intègre les vrais scores de `synthesize.py` |
| [`main.py`](../../radar/backend/main.py) | Pipeline 3 phases | Pipeline 4 phases (synthesize ajoutée) |

---

## Tests & benchmarks

### Résultats de bench sur 5 domaines

> Script : `python -m evals.bench_phases` depuis `radar/backend/`

| Domaine | UNDERSTAND | DISCOVER | ENRICH | **TOTAL** | Statut |
|---------|-----------|----------|--------|-----------|--------|
| linear.app | 12s | 107s | 17s | **136s** | ⚠️ lent |
| pennylane.com | 11s | 78s | 22s | **111s** | ⚠️ lent |
| mistral.ai | 45s | 132s | 17s | **194s** | ❌ très lent |
| cal.com | 10s | 59s | 23s | **92s** | ⚠️ limite |
| indy.fr | — | — | — | **52s** | ✅ OK |

**Observation clé** : DISCOVER est le goulot. 60–132s pour trouver des concurrents, alors que la cible est 20s. L'investigate à faire après switch en mode batched.

### Ce qu'on a vérifié (run indy.fr, 2026-05-19)

- Pipeline E2E complet ✅ — structurellement ça tourne
- Cache hit/miss ✅
- SSE streaming ✅ — progress events toutes les 7s
- Budget guards ✅ — hard cap bloque bien avant dépassement
- Synthesize scores ✅ — plus de placeholders [50,50,50,50,50,50]

### Ce qui reste à valider

- Dedup : indy.fr avait `freebe.me` en double dans l'output (G9)
- Source tracking : `sourcesScanned` toujours hardcodé à 0 (G8)
- Tail enrichment : 10/15 concurrents encore vides (G6)

---

## Braintrust — comment ça marche

**Braintrust** est notre système d'évaluation automatique des outputs du pipeline. Chaque phase a son eval file. On peut voir les résultats sur le dashboard Braintrust projet `"RADAR"`.

### Setup (à faire une fois)

```bash
cd RADAR/radar/backend
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)   # charge BRAINTRUST_API_KEY + autres clés
```

### Les 3 evals et ce qu'ils mesurent

| Fichier | Phase testée | Métriques |
|---------|-------------|-----------|
| [`eval_understand.py`](../../radar/backend/evals/eval_understand.py) | Phase 1 — UNDERSTAND | Couverture des champs (funding, HQ, marchés...), qualité du geocoding |
| [`eval_discover.py`](../../radar/backend/evals/eval_discover.py) | Phase 2 — DISCOVER | **score_count** : ≥10 concurrents = parfait, ≥5 = passable. **score_relevance** : LLM juge si les boîtes trouvées sont vraiment des concurrents. **score_data_quality** : % concurrents avec website + one_liner |
| [`eval_enrich.py`](../../radar/backend/evals/eval_enrich.py) | Phase 3 — ENRICH | **pricing_coverage** : % concurrents avec pricing source_url. **signals_quality** : LLM juge si les signaux sont substantiels (pas generiques). **stub_shape** : vérifie que le cap MAX_ENRICH est respecté |

### Comment lancer un eval

```bash
# Depuis RADAR/radar/backend/ avec venv activé
braintrust eval evals/eval_understand.py
braintrust eval evals/eval_discover.py
braintrust eval evals/eval_enrich.py
```

> ⚠️ Chaque eval découvre + enrich = appels Linkup réels. Coût par run ≈ €0.11 (understand + discover). Utiliser avec modération.

### Ce que Braintrust a révélé

- UNDERSTAND : champs de funding bien extraits, geocoding fiable via Nominatim
- DISCOVER : relevance OK sur les gros domaines (linear, pennylane), plus fragile sur les petits
- ENRICH : pricing source_url manquante sur ~40% des concurrents → G6 (tail enrichment)

---

## Les scripts à connaître

### Scripts d'évaluation / dev

| Script | Commande | Coût | Usage |
|--------|---------|------|-------|
| [eval_e2e_simple.py](../../radar/backend/evals/eval_e2e_simple.py) | `python evals/eval_e2e_simple.py linear.app` | ≈ €0.65 | Valider un domaine complet + injecter en cache démo |
| eval_e2e_simple.py (animation) | `python evals/eval_e2e_simple.py linear.app --no-cache` | ≈ €0.65 | Forcer le pipeline live (SSE animation visible) |
| [bench_phases.py](../../radar/backend/evals/bench_phases.py) | `python -m evals.bench_phases` | ≈ €0.50/domaine | Mesurer les durées par phase. Résultats → `evals/bench_results.csv` |
| [probe_post_understand.py](../../radar/backend/evals/probe_post_understand.py) | `python -m evals.probe_post_understand doctolib.fr` | ≈ €0.11 | Tester DISCOVER+ENRICH depuis un UNDERSTAND en cache (économise le understand) |
| [recover_indy.py](../../radar/backend/evals/recover_indy.py) | `python evals/recover_indy.py` | ≈ €0.11 | Récupérer un job Linkup interrompu. **Éditer JOB_ID + DOMAIN en dur avant de lancer.** |

### Tester une phase isolée

```bash
# Depuis RADAR/radar/backend/ avec venv activé
python -m pipeline.understand linear.app
python -m pipeline.discover linear.app          # nécessite un profile CompanyProfile
python -m pipeline.synthesize pipeline_run.json  # prend un PipelineRun JSON en argument
```

### Lancer le backend complet

```bash
cd RADAR/radar/backend
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)

# Dev (1 concurrent enrichi = €0.11/scan)
RADAR_MAX_ENRICH=1 uvicorn main:app --reload --port 8000

# Prod-like (5 concurrents = €1.61/scan)
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd RADAR/radar/frontend
npm install
npm run dev   # port 3000 → http://localhost:3000
```

---

## Gaps ouverts — par priorité

### Blockers avant démo

| ID | Problème | Impact démo | Action | Durée est. |
|----|---------|------------|--------|-----------|
| **G3** | Pre-cache 0/5 boîtes démo (Doctolib, Notion, Slite, Alan, Pennylane) | ❌ Si le pipeline plante en live = démo morte | `python evals/eval_e2e_simple.py doctolib.fr` × 5 — APRÈS fix data layer | 30 min |
| **G8** | `sourcesScanned = 0` hardcodé dans transform.py | ❌ "Sources tracées" est la narrative clé du pitch | Propager `source_urls` depuis Linkup → CompetitorProfile → RadarOutput | 1-2h |
| **G10** | Frontend prod (1 page de cards) ≠ prototype (9 screens : Compare/Timeline/Radar chart) | ❌ La démo ne ressemble pas à la vision | Décision produit : port prototype HTML ou build manquant en Next.js | TBD |

### High priority

| ID | Problème | Action | Durée est. |
|----|---------|--------|-----------|
| **G6** | 10/15 concurrents = stubs vides (pas de pricing/features) | Activer mode batched (`RADAR_ENRICH_MODE=batched`) et valider output | 1h |
| **G2** | DISCOVER 5× trop lent (60-132s, cible 20s) | Re-mesurer après G6 fix. Investiguer si Linkup /search deep peut être parallelisé | 2-3h |
| **G9** | `freebe.me` en double dans output indy.fr | Fix normalisation URL dans `utils/dedup.py` (strip protocol/www/path avant compare) | 30 min |

### Medium / post-démo

| ID | Problème |
|----|---------|
| **G4** | Deploy 0 setup — Vercel (frontend) + Railway/Render (backend) — J-2 max |
| **G5** | Types Pydantic ↔ TypeScript sync manuelle (drift risk, acceptable hackathon) |

---

## Pour démarrer (setup complet)

```bash
# 1. Venv + dépendances backend
cd /Users/paul.pietra/Dev/GATRA/RADAR/radar/backend
python3 -m venv .venv                       # si pas encore fait
source .venv/bin/activate
pip install -r requirements.txt

# 2. Variables d'environnement (créer backend/.env si absent)
# Contenu minimal :
# LINKUP_API_KEY=...
# ANTHROPIC_API_KEY=...
# BRAINTRUST_API_KEY=...         (pour les evals)
# NOMINATIM_USER_AGENT=radar-hackathon
export $(grep -v '^#' .env | xargs)

# 3. Backend
RADAR_MAX_ENRICH=1 uvicorn main:app --reload --port 8000

# 4. Frontend (autre terminal)
cd /Users/paul.pietra/Dev/GATRA/RADAR/radar/frontend
npm install && npm run dev

# 5. Tester que tout tourne
curl -X POST http://localhost:8000/scan -H "Content-Type: application/json" \
  -d '{"url": "linear.app"}'
```

---

## Règles à ne pas oublier

### Budget Linkup (critique)

```
Hard cap : €5/jour  → BudgetExceededError levé avant l'appel
Warn cap : €3/jour  → Warning dans les logs
Kill switch d'urgence : export RADAR_KILL_SWITCH=1 → bloque TOUT
Ledger des dépenses : radar/backend/cache/linkup_usage.jsonl
```

**En dev : toujours lancer avec `RADAR_MAX_ENRICH=1`** (sinon 5 × €1.50 = €7.50 → bloqué par le cap de toute façon mais autant ne pas déclencher l'erreur).

### Règles de code non négociables

| Règle | Pourquoi |
|-------|---------|
| **Ne jamais demander des coordonnées GPS à Linkup** | Linkup invente des coords plausibles mais fausses. Passer par `utils/geocoding.py` (Nominatim) |
| **Tout champ Linkup/Claude = DataPoint** | Pattern `{value, confidence, source_url, extracted_at}` — essentiel pour le source tracking |
| **Si Linkup retourne vide → `DataPoint(value=None, confidence="low")`** | Jamais halluciner de données |
| **Cache avant tout appel** | Clé `radar_{domain}_{YYYY-MM-DD}` — évite de re-payer Linkup pour les démos |
| **Si modèle Pydantic modifié → update types TypeScript** | `radar/frontend/src/types/index.ts` — sync manuelle obligatoire |
| **Ne pas appeler Linkup en boucle pour debugger** | Utiliser les fixtures dans `tests/fixtures/` ou le cache probe |

### Structure des fichiers clés

```
RADAR/
├── docs/Learning/
│   ├── ARCHITECTURE.md     ← pipeline technique détaillé (source de vérité)
│   └── HANDOFF.md          ← ce document
├── CLAUDE/CLAUDE.md        ← instructions pour l'IA (stack, règles, env vars)
├── STATUS.yaml             ← état du projet (health, bench, gaps) — tenir à jour
└── radar/
    ├── backend/
    │   ├── main.py              ← FastAPI app
    │   ├── pipeline/            ← understand · discover · enrich · synthesize · transform
    │   ├── clients/             ← linkup_client · claude_client
    │   ├── models/              ← CompanyProfile · CompetitorProfile · PipelineRun
    │   ├── evals/               ← scripts de test et bench
    │   ├── utils/               ← cache · geocoding · dedup
    │   └── cache/               ← JSON cache local (gitignored)
    └── frontend/
        ├── src/
        │   ├── pages/index.tsx  ← page principale
        │   ├── components/      ← CompanyCard · CompetitorGrid · OperationsConsole...
        │   └── design-system/   ← tokens.ts · tailwind.preset.ts (source of truth UI)
        └── package.json
```

---

*Généré le 2026-05-23 · Basé sur commit `51b2e9b` (2026-05-19)*
