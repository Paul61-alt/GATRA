# Radar — Architecture

> Une URL en entrée → 3 phases Python → interface React avec l'analyse concurrentielle.

---

## Pipeline en un coup d'œil

```
URL saisie
    │
    ▼
[POST /analyze]  ──── cache hit ? → JSON immédiat
    │
    ▼
Phase 1 — UNDERSTAND (~10-45s)
    │  1 appel Linkup → profil complet du sujet
    ▼
Phase 2 — DISCOVER (~60-130s)
    │  1 appel Linkup deep → 15 concurrents directs
    ▼
Phase 3 — ENRICH (~20s)
    │  30 appels Linkup en batch simultané (2 par concurrent)
    ▼
Phase 4 — TRANSFORM (~0s)
    │  Mise en forme pour le frontend
    ▼
data.js → React affiche l'analyse
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

---

### Phase 2 — DISCOVER
`pipeline/discover.py`

| | |
|---|---|
| **Ce qu'il fait** | Trouve 15 concurrents directs avec contexte |
| **Endpoint Linkup** | `POST /v1/search` |
| **Paramètres** | `depth=deep` (jusqu'à 10 itérations, scrape multi-URL) · `outputType=structured` |
| **Input** | `CompanyProfile` du sujet (nom, positionnement, marchés) |
| **Output** | Liste de 15 `dict` — nom, site, HQ, funding stage, one-liner, différenciateur |
| **Durée** | ~60-130s ← **goulot principal** |
| **Appels Linkup** | 1 (mais Linkup fait jusqu'à 10 sous-requêtes en interne) |

---

### Phase 3 — ENRICH
`pipeline/enrich.py`

| | |
|---|---|
| **Ce qu'il fait** | Profil concurrent approfondi via agent autonome Linkup Research |
| **Endpoint Linkup** | `POST /v1/tasks` (batch) avec `type=research` |
| **Paramètres** | 1 Research par concurrent · `mode=Investigate` · `depth=S` · `outputType=structured` + schema JSON |
| **Contenu** | Pricing tiers exacts, signaux LinkedIn fondateurs, funding complet, signaux produit typés, faiblesses |
| **Input** | Les 15 concurrents de Discover |
| **Output** | 15 `CompetitorProfile` — pricing structuré, LinkedIn URL + posts fondateurs, signals typés (funding/product/hiring…) |
| **Durée** | ~2-5 min (Linkup traite les 15 Research jobs en parallèle côté serveur) |
| **Appels Linkup** | 1 batch = 15 Research jobs simultanés |
| **Coût** | ~$3.75/run (15 × $0.25 depth=S) |

---

### Phase 4 — TRANSFORM
`pipeline/transform.py` + `generate_data_js.py`

| | |
|---|---|
| **Ce qu'il fait** | Convertit les données pipeline au format attendu par le frontend |
| **Endpoint Linkup** | Aucun |
| **Input** | `PipelineRun` (CompanyProfile + 15 CompetitorProfile) |
| **Output** | `RadarOutput` → `data.js` (chargé par React) |
| **Durée** | ~0s |
| **⚠ Placeholders** | `similarity=0.5`, `threat="medium"`, `features=[]`, `radar.scores=[50…]`, `pricingTiers=[]` |

---

## Endpoints Linkup utilisés

| Endpoint | Où | Ce qu'il fait | Latence |
|---|---|---|---|
| `POST /v1/search` · `depth=standard` | UNDERSTAND | 1 recherche + extraction structurée JSON | ~10-45s |
| `POST /v1/search` · `depth=deep` | DISCOVER | Jusqu'à 10 itérations, scrape multi-URL | ~60-130s |
| `POST /v1/tasks` avec `type=research` | ENRICH | Batch de 15 Research jobs en parallèle | ~2-5 min |
| `GET /v1/tasks/{id}` | ENRICH | Polling jusqu'à completion (max 600s) | — |
| `POST /v1/fetch` | Optionnel | Charge une URL spécifique → markdown | ~1s |
| `POST /v1/research` | **Non utilisé encore** | Agent autonome, rapport multi-sources (beta) | 2-20 min |

---

## Clients et utilitaires

| Fichier | Rôle |
|---|---|
| `clients/linkup_client.py` | Wrapper HTTP Linkup — retry, budget quotidien, toutes les méthodes |
| `clients/claude_client.py` | Wrapper Anthropic SDK — prévu pour Phase 5 (Synthesize) |
| `utils/geocoding.py` | Nominatim (OpenStreetMap) — lat/lng depuis ville+pays, 1 req/s max |
| `utils/cache.py` | Cache fichier JSON par domaine+date — évite de re-appeler Linkup |
| `utils/dedup.py` | Normalise les domaines et dédoublonne les concurrents |

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

## Modèles de données

```
CompanyProfile      ← sujet (understand.py)
CompetitorProfile   ← chaque concurrent (enrich.py)
PipelineRun         ← enveloppe : id + status + les deux ci-dessus
    ↓ transform.py
RadarOutput         ← format exact du frontend (camelCase JSON)
    ↓ generate_data_js.py
data.js             ← window.RADAR_DATA = {...}
```

---

## Pour lancer le pipeline

```bash
# Serveur complet
cd RADAR/radar/backend && uvicorn main:app --reload

# Tester une phase isolée
python3 -m pipeline.understand linear.app
python3 -m pipeline.enrich '[{"name":"Notion","website":"notion.so"}]'

# POC Research endpoint (Linkup beta)
python3 -m evals.poc_research notion.so
python3 -m evals.poc_research notion.so --depth M
```
