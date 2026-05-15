# Radar — Architecture & Pipeline

> Document de référence pour comprendre ce qui a été construit, comment chaque brique fonctionne et dans quel ordre elles s'exécutent.

---

## Vue d'ensemble en une phrase

Radar prend une URL en entrée, fait tourner un pipeline Python en 3 phases (comprendre → découvrir → enrichir), et produit un fichier `data.js` que le frontend React charge directement pour afficher l'analyse concurrentielle.

---

## Arborescence

```
RADAR/radar/
├── backend/
│   ├── main.py                        # Serveur FastAPI — point d'entrée HTTP
│   ├── generate_data_js.py            # Sérialiseur : RadarOutput → data.js   ← nouveau
│   │
│   ├── models/
│   │   ├── company.py                 # CompanyProfile (le sujet)
│   │   ├── competitor.py              # CompetitorProfile (les concurrents)
│   │   ├── pipeline.py                # PipelineRun — enveloppe globale d'un scan
│   │   └── radar_output.py            # RadarOutput — format attendu par le frontend  ← nouveau
│   │
│   ├── pipeline/
│   │   ├── understand.py              # Phase 1 : profil du sujet via Linkup
│   │   ├── discover.py                # Phase 2 : liste de 15 concurrents via Linkup
│   │   ├── enrich.py                  # Phase 3 : enrichit chaque concurrent (pricing, signaux)
│   │   └── transform.py              # PipelineRun → RadarOutput                  ← nouveau
│   │
│   ├── clients/
│   │   ├── linkup_client.py           # Wrapper HTTP pour l'API Linkup
│   │   └── claude_client.py           # Wrapper Anthropic SDK pour Claude
│   │
│   └── utils/
│       ├── cache.py                   # Cache fichier JSON (1 fichier par domaine + date)
│       ├── geocoding.py               # Lat/lng via Nominatim (OpenStreetMap)
│       └── dedup.py                   # Dédoublonnage des concurrents par domaine
│
└── frontend/
    ├── index.html                     # Point d'entrée — charge tous les scripts
    ├── data.js                        # Données générées par le pipeline  ← produit
    ├── styles.css                     # Design system (tokens CSS, composants)
    ├── components.jsx                 # Primitives UI partagées (Sidebar, Topbar, icons…)
    ├── app.jsx                        # Routing entre les 3 vues (Home / New scan / Résultats)
    └── screens-*.jsx                  # Un fichier par écran (Overview, List, Compare…)
```

---

## Le pipeline — 3 phases + transform

### Flux complet

```
URL saisie
    │
    ▼
[POST /analyze] (main.py)
    │
    ├─ Cache hit ? → retourne immédiatement le JSON mis en cache
    │
    ▼
Phase 1 — UNDERSTAND (understand.py)
    │  Linkup search structuré → nom, HQ, employés, funding, marchés, signaux
    │  Geocoding Nominatim → lat/lng du HQ
    │  → CompanyProfile
    │
    ▼
Phase 2 — DISCOVER (discover.py)
    │  Linkup search deep → 15 concurrents directs avec one-liner, funding stage, HQ
    │  Dédup par domaine normalisé
    │  → list[dict] (raw competitor data)
    │
    ▼
Phase 3 — ENRICH (enrich.py)
    │  Pour chaque concurrent, 2 tâches Linkup en batch :
    │    - pricing ("X pricing plans tiers cost 2025")
    │    - signaux récents ("X funding news features since 2024-11-01")
    │  Geocoding concurrent en parallèle
    │  → list[CompetitorProfile]
    │
    ▼
PipelineRun (pipeline.py)
    │  Enveloppe : id, domain, status, created_at, company_profile, competitors
    │  Sérialisé en JSON → cache disque
    │
    ▼
transform.py  ← NOUVEAU
    │  PipelineRun → RadarOutput
    │  Mappe les champs disponibles, placeholders pour les champs manquants
    │
    ▼
generate_data_js.py  ← NOUVEAU
    │  RadarOutput → data.js (window.RADAR_DATA = {...})
    │
    ▼
frontend/data.js  → chargé par index.html → React affiche l'analyse
```

---

## Explication fichier par fichier

### `main.py` — Le serveur

FastAPI, 2 routes :

- `POST /analyze` — reçoit `{"url": "linq.io"}`, orchestre les 3 phases, met en cache, renvoie le JSON du `PipelineRun`
- `GET /health` — healthcheck

Le cache est vérifié **avant** d'appeler Linkup. Si un résultat existe pour ce domaine aujourd'hui, il est renvoyé immédiatement (clé = `domaine_YYYY-MM-DD.json`).

Les clients Linkup et Claude sont initialisés une fois au démarrage via le `lifespan` FastAPI et attachés à `app.state`.

---

### `clients/linkup_client.py` — L'accès web

Linkup est le moteur de recherche web du pipeline. Il transforme une requête en langage naturel en réponse structurée extraite de sources réelles.

**Méthodes utilisées :**

| Méthode | Usage dans le pipeline | Ce qu'elle fait |
|---|---|---|
| `search()` | Phase 1 + 2 | Requête + schéma JSON → réponse structurée extraite du web |
| `tasks()` | Phase 3 | Batch de requêtes en parallèle, polling jusqu'à completion |
| `fetch()` | Optionnel | Charge une URL spécifique (avec fallback search si bloqué) |

**Retry** : 3 tentatives avec backoff exponentiel sur les codes 429/500/502/503.

**Timeout** : 60s par requête POST, 30s par GET. Les tâches batch attendent jusqu'à 300s.

---

### `clients/claude_client.py` — L'intelligence

Claude Sonnet 4 utilisé pour les extractions JSON structurées.

**Méthodes :**

| Méthode | Usage | Ce qu'elle fait |
|---|---|---|
| `extract_json()` | Analyse texte → JSON | Appel Claude, parse le premier objet JSON trouvé |
| `extract_model()` | JSON → Pydantic | `extract_json` + `model_validate` |
| `complete()` | Texte libre | Completion sans parsing |

> **Note** : dans le pipeline actuel v1, Claude n'est pas encore appelé dans les 3 phases — Linkup fait l'extraction directement en mode `structured`. Claude est prévu pour la **Phase 4 (synthesize)** : calculer similarity, threat, matrice de features, scores radar.

---

### `pipeline/understand.py` — Phase 1

Un seul appel Linkup avec un schéma JSON détaillé. Linkup scrape le web et retourne les données structurées.

**Données extraites :**
- Nom officiel, résumé, année de fondation
- HQ city + country → geocoding Nominatim → lat/lng
- Employés, funding total EUR, rounds avec montants et leads
- Positionnement (1 phrase), marchés, signaux de croissance

**Sortie :** `CompanyProfile`

---

### `pipeline/discover.py` — Phase 2

Un appel Linkup en mode `deep` (plus lent, plus complet) avec le profil du sujet pour contexte.

**Prompt dynamique :** inclut le nom, domaine, positionnement et marchés du sujet pour que Linkup comprenne le segment.

**Données par concurrent :** nom, URL, HQ, année, funding stage, headcount approximatif, one-liner, différenciateur.

**Dédup** (`utils/dedup.py`) : normalise les domaines (`https://www.X.com` → `x.com`) et élimine les doublons.

**Sortie :** `list[dict]` (max 15 concurrents)

---

### `pipeline/enrich.py` — Phase 3

Pour chaque concurrent, **2 requêtes Linkup en batch** (toutes soumises en parallèle) :
1. Pricing : `"{nom} pricing plans tiers cost 2025"`
2. Signaux : `"{nom} funding news features since 2024-11-01"`

**Geocoding en parallèle** via `asyncio.gather` — tous les HQ géocodés simultanément.

**Parsing pricing** : actuellement basique (confidence "low") — le texte brut de Linkup est capturé mais pas encore analysé finement. Prévu pour Phase 4.

**Sortie :** `list[CompetitorProfile]`

---

### `utils/cache.py` — Le cache fichier

Stocke chaque résultat dans `RADAR/cache/domaine_YYYY-MM-DD.json`.

La clé inclut la date → le cache expire automatiquement le lendemain (sans TTL actif, juste par convention de nommage).

**Fonctions :** `get(domain)`, `set(domain, data)`, `invalidate(domain)`

---

### `utils/geocoding.py` — Coordonnées GPS

Utilise l'API gratuite **Nominatim** (OpenStreetMap). Rate-limit enforced à 1 req/s (condition d'utilisation Nominatim).

Retourne `(lat, lng)` ou `None` si échec.

---

### `models/` — Les structures de données

**Existants :**

| Modèle | Contient |
|---|---|
| `DataPoint` | `value + confidence + source_url + extracted_at` — encapsule toute donnée extraite |
| `CompanyProfile` | Profil complet du sujet (funding, HQ, marchés, signaux…) |
| `FundingRound` | Un tour de table : round/amount_eur/date/lead |
| `CompetitorProfile` | Profil d'un concurrent (one_liner, pricing brut, signaux récents) |
| `PipelineRun` | Enveloppe : id, status, company_profile, competitors[], from_cache |

**Nouveau :**

| Modèle | Rôle |
|---|---|
| `RadarOutput` | Format exact attendu par `data.js` — tous les champs du frontend |
| `Company` | Un sujet ou concurrent avec tous les champs visuels |
| `FundingInfo` | Résumé funding : total, last_round, last_round_at |
| `PricingSummary` | Résumé pricing : model, starts_at, mention |
| `FundingEvent` | Un tour pour la timeline : y, q, amt, round |
| `Feature` | Une ligne de la matrice : group + label |
| `PricingTier` | Un tier tarifaire : name, price, per, features[] |
| `RadarConfig` | Axes + scores + définitions du radar chart |
| `ScanQuery` | Métadonnées du scan : url, name, scanned_at, duration_ms |

**Convention :** tous les modèles `RadarOutput` utilisent `alias_generator=to_camel` — les noms Python sont `snake_case` mais le JSON produit est `camelCase` (ce que le JS attend).

---

### `pipeline/transform.py` — Le pont ← NOUVEAU

Fonction centrale : `pipeline_run_to_radar_output(run: PipelineRun) -> RadarOutput`

**Ce qu'il mappe :**

| Champ PipelineRun | → | Champ RadarOutput |
|---|---|---|
| `company_profile.name` | | `subject.name` |
| `company_profile.summary` | | `subject.tagline` |
| `company_profile.hq.lat/lng` | | `subject.hqCoords` |
| `company_profile.markets[primary].label` | | `subject.category` |
| `company_profile.funding.total_raised_eur` | | `subject.funding.total` |
| `company_profile.funding.rounds[].date` | | `funding[id][].y + .q` (trimestre calculé) |
| `competitor.one_liner` | | `competitor.tagline` |
| `competitor.website` | | `competitor.domain` (normalisé) |
| `competitor.employee_count.value` | | `competitor.employees` (parse "200-500" → 200) |

**Placeholders (à remplacer par Phase 4) :**
- `similarity` : `0.5` pour tous les concurrents
- `threat` : `"medium"` pour tous
- `features`, `capabilities` : listes vides
- `radar.scores` : `[50, 50, 50, 50, 50, 50]` (neutre)
- `pricing tiers` : listes vides

**Helpers internes :**
- `_slug(name)` → ID unique : `"Pylon Pay"` → `"pylon_pay"`
- `_date_to_y_q("2024-09")` → `(2024, 3)` (trimestre)
- `_parse_domain("https://www.vex.finance")` → `"vex.finance"`
- `_format_hq(hq)` → `"San Francisco, CA"`

---

### `generate_data_js.py` — Le sérialiseur ← NOUVEAU

Fonction : `generate_data_js(data: RadarOutput, output_path) -> None`

1. `data.model_dump(by_alias=True, mode="json", exclude_none=True)` → dict camelCase sans les `None`
2. Trie les concurrents par `similarity` décroissant pour `allCompanies`
3. Écrit :
```js
// Auto-generated — do not edit manually.
window.RADAR_DATA = { ...tout le JSON... };

window.RADAR_DATA.allCompanies = [ sujet, ...concurrents triés ];
```

**CLI :**
```bash
python generate_data_js.py cache/linq.io_2026-05-13.json frontend/data.js
```

**En Python :**
```python
from pipeline.transform import pipeline_run_to_radar_output
from generate_data_js import generate_data_js

run = PipelineRun.model_validate_json(Path("cache.json").read_text())
generate_data_js(pipeline_run_to_radar_output(run), "frontend/data.js")
```

---

## Ce qui manque — Phase 4 (synthesize)

Ces champs sont des placeholders dans le transform actuel. Une **Phase 4** les calculera via Claude :

| Champ | Valeur actuelle | Ce que Phase 4 fera |
|---|---|---|
| `similarity` | `0.5` fixe | Claude compare les profils → score 0–1 |
| `threat` | `"medium"` fixe | Claude évalue funding + similarity → high/med/low |
| `features[]` | `[]` | Claude génère la liste des features à comparer |
| `capabilities{}` | `{}` | Claude évalue chaque concurrent sur chaque feature |
| `radar.scores` | `[50…]` | Claude note sur 6 axes (0–100) |
| `pricing tiers` | `[]` | Claude parse le texte brut Linkup |
| `arr, customers` | `None` | Claude estime depuis les signaux publics |

Ce module sera branché dans `main.py` entre `enrich.run()` et la construction du `PipelineRun`.

---

## Le frontend — comment il charge les données

Le frontend est un **SPA React sans bundler** : Babel standalone compile les JSX dans le navigateur.

`index.html` charge les scripts dans cet ordre :
1. `data.js` — définit `window.RADAR_DATA`
2. `tweaks-panel.jsx` — panneau de réglages flottant
3. `components.jsx` — primitives UI (LogoMark, Sidebar, Bar, icons…)
4. `screens-*.jsx` — un écran par fichier (8 au total)
5. `app.jsx` — routing + rendu React

Chaque écran reçoit `data` (= `window.RADAR_DATA`) en prop et affiche sa vue.

**Pour utiliser les vraies données :** il suffit de remplacer `frontend/data.js` par le fichier généré par `generate_data_js.py`. Aucune modification du frontend nécessaire.

---

## Dépendances

```
fastapi          Serveur HTTP async
uvicorn          ASGI runtime
httpx            Requêtes HTTP async (Linkup, Nominatim)
anthropic        SDK officiel Claude
pydantic>=2.7    Validation + sérialisation des modèles
python-dotenv    Chargement du .env
```

Pas de base de données. Pas de Redis. Tout est en mémoire + fichiers JSON locaux.
