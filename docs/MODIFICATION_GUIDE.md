# RADAR — Guide de modification

Carte du code pour modifier algos, prompts, seuils sans tout casser. Pour Paul + partenaire.

---

## Vue d'ensemble du pipeline

```
URL entrée
   │
   ▼
[1. UNDERSTAND]  ──► profil de l'entreprise (subject)
   │
   ▼
[2. DISCOVER]    ──► liste 15-20 concurrents candidats
   │
   ▼
[3. ENRICH]      ──► profils détaillés des concurrents (pricing, funding, signaux)
   │
   ▼
[4. SYNTHESIZE]  ──► scores radar (6 axes)
   │
   ▼
[5. TRANSFORM]   ──► RadarOutput (format frontend)
```

Chaque phase = 1 fichier dans `radar/backend/pipeline/`.

---

## Quick reference — "Je veux changer X, je vais où ?"

| Tu veux changer... | Fichier | Ligne | Fonction |
|---|---|---|---|
| **Prompt qui calcule le niveau de menace** | `clients/claude_client.py` | L303 | `score_threats_candidates()` |
| **Seuils high/medium/low** | `pipeline/transform.py` | L174 | `_threat_from_score()` |
| **Algo de similarité (Jaccard)** | `pipeline/transform.py` | L191 | `_compute_similarity()` |
| **Liste de stopwords (mots ignorés)** | `pipeline/transform.py` | L183 | `_STOPWORDS` |
| **Queries de recherche Linkup pour Discover** | `pipeline/discover.py` | L30 | `_build_queries()` |
| **Prompt du fallback Claude (knowledge-base)** | `clients/claude_client.py` | L203 | `discover_competitors_fallback()` |
| **Prompt pour merger résultats Discover** | `clients/claude_client.py` | L252 | `extract_discover_candidates()` |
| **Prompt pour profiler 1 concurrent (Enrich)** | `pipeline/enrich.py` | L141 | `_research_query()` |
| **Prompt pour batch Enrich (mode défaut)** | `pipeline/enrich.py` | L398 | `_batched_query()` |
| **Heuristiques scores radar (Breadth/Depth/etc)** | `pipeline/synthesize.py` | L65 | `_score_subject()` / `_score_competitor()` |
| **Schéma JSON attendu de Linkup Discover** | `pipeline/discover.py` | — | (pas de schéma — réponse texte) |
| **Schéma JSON attendu Linkup Enrich** | `pipeline/enrich.py` | L47 | `COMPETITOR_SCHEMA` |
| **Budgets quotidiens (€)** | `clients/linkup_client.py` | L26-27 | `DAILY_HARD_CAP_EUR` / `DAILY_WARN_CAP_EUR` |
| **Nombre max de concurrents enrichis (legacy)** | `pipeline/enrich.py` | L42 | `MAX_ENRICH` |
| **Endpoints API (URL d'entrée)** | `main.py` | L110+ | `/analyze`, `/scan`, `/scan/stream`, `/scan/discover`, `/scan/enrich` |
| **Modèle Claude utilisé** | `clients/claude_client.py` | L12 | `MODEL` |

---

## 1. UNDERSTAND — profil de l'entreprise

**Fichier** : `radar/backend/pipeline/understand.py`

**Ce qu'il fait** : prend un domaine (ex: makipeople.com), retourne un `CompanyProfile` complet (employees, funding, customers, positioning, etc.) en appelant Linkup `/fetch` + `/search` + Claude pour merger.

| Élément | Ligne | Quoi modifier |
|---|---|---|
| `_SEGMENT_MAP` | L39 | Mots français/anglais qui mappent vers nos 5 segments (Grand compte, ETI, PME, Startup, Consumer) |
| `_LINKEDIN_SCHEMA` | L73 | Champs attendus de la recherche LinkedIn (employees, customers, growth signals) |
| `_NEWS_SCHEMA` | L118 | Champs attendus des news (funding, events) |
| `_fetch_company_pages()` | L256 | Quelles URLs scrapper (homepage, pricing, customers, about, blog) |
| `_PAGE_EXTRACT_SYSTEM` | L306 | Prompt Claude pour extraire le profil depuis le contenu web |
| `_linkedin_query()` | L385 | Query envoyée à Linkup pour info LinkedIn |
| `_news_query()` | L408 | Query envoyée à Linkup pour news récentes |
| `_merge_data()` | L443 | Logique de merge entre les 3 sources (pages + LinkedIn + news) |
| `run()` | L547 | Orchestrateur — séquence d'appels |

---

## 2. DISCOVER — trouver les concurrents

**Fichier** : `radar/backend/pipeline/discover.py`

**Architecture v2** : 3 recherches parallèles standard (au lieu d'1 deep) → Claude merge → optional threat scoring.

**Fallback** : si Linkup retourne rien, Claude pioche dans sa knowledge base (gratuit).

| Élément | Ligne | Quoi modifier |
|---|---|---|
| `_MAX_CANDIDATES` | L27 | Nombre max de concurrents renvoyés (défaut 20) |
| `_build_queries()` | L30 | Les 3 queries de recherche Linkup (alternatives, market landscape, vs-comparisons) |
| `_claude_fallback()` | L61 | Logique du fallback Claude (utilisée si Linkup vide) |
| `run()` | L143 | Orchestrateur principal du discover |
| Step 3 — threat scoring | L259 | Appel à `score_threats_candidates` + tri |

**Coût** : ~€0.018 (3 × €0.006 standard search) vs ~€0.055 avant.

---

## 3. ENRICH — profil détaillé des concurrents

**Fichier** : `radar/backend/pipeline/enrich.py`

**2 modes** (`RADAR_ENRICH_MODE` env var) :
- **`batched`** (défaut) : 1 seul appel `/research` pour TOUS les concurrents → €1.50 fixe
- **`legacy`** : N appels `/research` (top-1 en depth M, reste en depth S) → €1.50 + N × €0.25

| Élément | Ligne | Quoi modifier |
|---|---|---|
| `ENRICH_MODE` | L41 | Mode batched ou legacy |
| `MAX_ENRICH` | L42 | Cap nombre de concurrents enrichis en mode legacy (défaut 5) |
| `DEPTH_TOP` / `DEPTH_REST` / `DEPTH_BATCH` | L43-45 | Profondeur Linkup (S=€0.25, M=€0.50, L=€1.50, XL=€2.50) |
| `COMPETITOR_SCHEMA` | L47 | Tous les champs extraits par concurrent (pricing, funding, customers, signals, weaknesses) |
| `_research_query()` | L141 | Prompt pour profiler 1 concurrent (mode legacy) |
| `_batched_query()` | L398 | Prompt pour profiler N concurrents en 1 appel (mode batched) |
| `_parse_result()` | L170 | Comment parser la réponse Linkup → `CompetitorProfile` |
| `_stub()` | L320 | Profil minimal si enrich échoue (utilise les infos discover) |

**Variables env** :
- `RADAR_ENRICH_MODE=batched|legacy`
- `RADAR_MAX_ENRICH=5` (legacy uniquement)

---

## 4. SYNTHESIZE — scores radar 6 axes

**Fichier** : `radar/backend/pipeline/synthesize.py`

**6 axes calculés** : Breadth, Depth, Global, Developer, Pricing, Trust. Chacun 0-100.

**Pas de LLM** : heuristiques pures basées sur les données extraites. Gratuit + instantané.

| Élément | Ligne | Quoi modifier |
|---|---|---|
| `AXES` | L21 | Noms des 6 axes affichés dans le radar |
| `_DEV_PATTERN` | L23 | Regex pour détecter signaux "developer" (api/sdk/webhook/etc) |
| `_score_subject()` | L65 | Comment scorer l'entreprise subject sur chaque axe |
| `_score_competitor()` | L141 | Comment scorer chaque concurrent sur chaque axe |
| `run()` | L224 | Orchestrateur |

**Formules clés (subject)** :
- Breadth = `len(features)*10 + len(verticals)*5 + len(customers)*5`
- Pricing : Freemium=85, Subscription=65, Enterprise=30
- Trust = `age*2 + employees/20 + funding/4M + customers*3 + investors*2`

**Pour ajouter un nouvel axe** : ajouter à `AXES` + écrire un calcul dans les 2 fonctions `_score_*`.

---

## 5. TRANSFORM — formater pour le frontend

**Fichier** : `radar/backend/pipeline/transform.py`

**Ce qu'il fait** : convertit `PipelineRun` (interne) → `RadarOutput` (format JSON frontend).

| Élément | Ligne | Quoi modifier |
|---|---|---|
| `_DEFAULT_RADAR_AXES` | L27 | Noms des 6 axes (doit matcher synthesize.py) |
| `_DEFAULT_RADAR_DEFS` | L28 | Tooltips qui définissent chaque axe |
| `_threat_from_score()` | L174 | **Seuils high/medium/low** (≥70/≥40/<40) |
| `_STOPWORDS` | L183 | Mots ignorés dans le calcul de similarité |
| `_compute_similarity()` | L191 | **Algo Jaccard** pour similarité subject↔competitor |
| `_map_subject()` | L121 | Mapping CompanyProfile → Company (frontend) |
| `_map_competitor()` | L233 | Mapping CompetitorProfile → Company (frontend) |
| `pipeline_run_to_radar_output()` | L272 | Orchestrateur final |

**Pour changer l'échelle de similarité** :
- L224 : `0.5 + jaccard * 4` → ex. `jaccard * 8` pour vraie échelle 0-1

**Pour changer les seuils threat** :
- L174-180 : ajuster les `if score >= 70` etc.

---

## 6. Clients (LLM + Search)

### `clients/claude_client.py` — Anthropic API

| Méthode | Ligne | À quoi ça sert |
|---|---|---|
| `MODEL` | L12 | Modèle Claude (défaut: `claude-sonnet-4-20250514`) |
| `extract_json()` | L22 | Wrapper bas-niveau : call Claude → parse JSON |
| `complete()` | L45 | Wrapper bas-niveau : call Claude → texte brut |
| `generate_vc_memo()` | L55 | Memo VC markdown pour 1 concurrent (4 sections) |
| `enrich_company_profile()` | L78 | Post-process : equity story + customer segments |
| `discover_competitors_fallback()` | L203 | **Fallback Discover (knowledge base)** |
| `extract_discover_candidates()` | L252 | Merge 3 résultats de search → liste de candidats |
| `score_threats_candidates()` | L303 | **Scoring 0-100 par concurrent (prompt LLM)** |
| `score_threats()` | L381 | Idem mais keyé par website (legacy) |

### `clients/linkup_client.py` — Linkup API

| Élément | Ligne | À quoi ça sert |
|---|---|---|
| `RESEARCH_COST_EUR` | L22 | Prix /research par depth (S/M/L/XL) |
| `SEARCH_COST_EUR` | L23 | Prix /search standard vs deep vs structured |
| `DAILY_HARD_CAP_EUR` | L26 | **Cap quotidien dur (défaut 5€)** — bloque si dépassé |
| `DAILY_WARN_CAP_EUR` | L27 | **Cap warning (défaut 3€)** — log alerte |
| `_LEDGER_PATH` | L35 | Chemin du carnet de bord JSONL des appels |
| `BudgetExceededError` | L30 | Exception levée si budget dépassé |
| `search()` | L200 | Wrapper /search (standard ou deep, avec ou sans schema) |
| `fetch()` | L227 | Wrapper /fetch (scrape une URL) |
| `research_and_wait()` | L317 | Wrapper /research (job long, attend complétion) |

**Variables env (Linkup)** :
- `RADAR_DAILY_HARD_CAP_EUR=5.0`
- `RADAR_DAILY_WARN_CAP_EUR=3.0`
- `RADAR_DAILY_BUDGET=50` (cap en nombre d'appels, séparé du cap €)
- `RADAR_KILL_SWITCH=1` (désactive tous les appels Linkup)

---

## 7. Models (formats de données)

Dossier : `radar/backend/models/`

| Fichier | Contient |
|---|---|
| `company.py` | `CompanyProfile` (subject) — funding, customers, growth signals, etc. |
| `competitor.py` | `DiscoverCandidate` (léger : name+domain+tagline) + `CompetitorProfile` (enrichi) |
| `pipeline.py` | `PipelineRun` — état global du scan (status, scores, threat_scores) |
| `radar_output.py` | `RadarOutput` — format final envoyé au frontend (camelCase) |

**Ajouter un champ** : édit le model Pydantic concerné + mappe-le dans `transform.py`.

---

## 8. Utils

Dossier : `radar/backend/utils/`

| Fichier | Rôle |
|---|---|
| `cache.py` | Cache JSON disque : `cache_get(key)` / `cache_set(key, data)` |
| `dedup.py` | `dedup_by_website()` + `normalize_domain()` |
| `geocoding.py` | Convertit city+country → (lat, lng) pour la carte |
| `data_js.py` | Génère le fichier `data.js` pour le frontend statique |

---

## 9. API endpoints (main.py)

**Fichier** : `radar/backend/main.py`

| Endpoint | Méthode | Ligne | Usage |
|---|---|---|---|
| `/analyze` | POST | L110 | Pipeline complet, retourne `PipelineRun` brut |
| `/scan` | POST | L171 | Pipeline complet, retourne `RadarOutput` (frontend-ready) |
| `/scan/stream` | POST | L221 | Comme `/scan` mais SSE (événements progressifs) |
| `/scan/discover` | POST | L332 | UNDERSTAND + DISCOVER seulement (rapide) |
| `/scan/enrich` | POST | L383 | ENRICH + SYNTHESIZE sur sélection VC (suite de discover) |
| `/health` | GET | L499 | Healthcheck |

**Rate limit** : `3/minute` par IP sur les endpoints scan.

**CORS** : configuré pour `localhost:3000`, `5173`, `8080` + `FRONTEND_URL` env var.

---

## Recettes courantes

### Ajouter un nouveau marché/positioning au pipeline
1. Pas besoin de toucher au code — `understand.py` extrait dynamiquement le marché depuis le contenu web.
2. Si tu veux forcer un mapping (ex: "edtech français" → "EdTech FR"), édit `_SEGMENT_MAP` dans `understand.py` L39.

### Rendre les recherches Discover plus ciblées
- Édit `_build_queries()` dans `discover.py` L30
- Ex: ajouter site:linkedin.com, retirer "2024 2025", changer "best" en "top emerging"

### Changer le ton du memo VC
- Édit le `system` prompt dans `generate_vc_memo()` claude_client.py L55-62

### Désactiver le fallback Claude (pour debug)
- Commente l'appel `_claude_fallback()` dans `discover.py` L212 et L243

### Tester sans payer Linkup
- `export RADAR_KILL_SWITCH=1` — tous les appels Linkup lèveront une erreur

### Forcer le mode legacy enrich (1 call par concurrent)
- `export RADAR_ENRICH_MODE=legacy RADAR_MAX_ENRICH=3`

---

## Variables d'environnement (récap)

| Var | Défaut | Effet |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Clé Claude (obligatoire) |
| `LINKUP_API_KEY` | — | Clé Linkup (obligatoire) |
| `RADAR_DAILY_HARD_CAP_EUR` | 5.0 | Cap quotidien Linkup en € |
| `RADAR_DAILY_WARN_CAP_EUR` | 3.0 | Seuil warning Linkup |
| `RADAR_DAILY_BUDGET` | 50 | Cap quotidien en nb d'appels |
| `RADAR_KILL_SWITCH` | (off) | Désactive tous les appels Linkup |
| `RADAR_ENRICH_MODE` | batched | `batched` ou `legacy` |
| `RADAR_MAX_ENRICH` | 5 | Cap concurrents enrichis (legacy only) |
| `RADAR_MAX_CONCURRENT` | 2 | Nb de scans simultanés autorisés |
| `FRONTEND_URL` | — | URL frontend pour CORS |

---

## Avant de toucher au code

1. **Toujours sur une branche feature** : `git checkout -b feat/X`
2. **Tester localement** : `python -m pipeline.discover linear.app` (pour discover)
3. **Vérifier le compilation** : `python -c "from pipeline.discover import run"`
4. **Comparer cache avant/après** : `radar/cache/radar_*.json`

## Pour aider Claude à comprendre quel fichier toucher

Quand tu lui demandes une modif, **donne-lui le chemin précis du fichier + la fonction** :
> ❌ "Change le calcul de threat"
> ✅ "Dans `pipeline/transform.py`, change `_threat_from_score()` L174 — passe le seuil high de 70 à 80"
