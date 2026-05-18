# CLAUDE.md — Radar
> Fichier de contexte pour Claude Code. Lis-le en entier avant toute tâche.

---

## 🎯 Projet & Contraintes

**Radar** est un outil de veille concurrentielle pour VCs. L'utilisateur colle une URL de startup → reçoit un memo concurrentiel structuré en < 60s.

- **Contexte** : Hackathon Linkup — deadline serrée, priorité = **ship > perfect**
- **Stack décidée, ne pas remettre en question** sauf si blocage technique clair
- **Pas de sur-ingénierie** : pas de Docker, pas de Redis, pas de queue complexe pour l'instant

---

## 🏗️ Architecture

### Pipeline en 3 phases (séquentiel → parallèle)

```
URL startup
    ↓
[PHASE 1 — UNDERSTAND] ~15s
  Linkup /search (depth=standard) + /fetch Crunchbase
  → CompanyProfile (Pydantic)
    ↓
[PHASE 2 — DISCOVER] ~20s
  Linkup /search (depth=deep)
  → Liste 15 concurrents déduplicés par `website`
    ↓
[PHASE 3 — ENRICH] ~60s
  Linkup /tasks (batch async) + /fetch pricing pages
  → CompetitorProfile × 15 (Pydantic) + PricingSignals
    ↓
Output JSON → Claude API extraction → Frontend React
```

### Structure de fichiers

```
radar/
├── CLAUDE.md                  ← ce fichier
├── backend/
│   ├── main.py                ← FastAPI app + routes
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── understand.py      ← Phase 1 : CompanyProfile
│   │   ├── discover.py        ← Phase 2 : competitor list
│   │   └── enrich.py          ← Phase 3 : CompetitorProfile + PricingSignals
│   ├── clients/
│   │   ├── linkup_client.py   ← wrapper Linkup API (retry, fallback)
│   │   └── claude_client.py   ← wrapper Claude API (extraction JSON)
│   ├── models/
│   │   ├── company.py         ← CompanyProfile, DataPoint
│   │   ├── competitor.py      ← CompetitorProfile, PricingSignal
│   │   └── pipeline.py        ← PipelineRun, PipelineStatus
│   ├── utils/
│   │   ├── geocoding.py       ← Nominatim (OpenStreetMap) — PAS Linkup pour les coords
│   │   ├── cache.py           ← cache JSON fichier, clé = company_domain+date
│   │   └── dedup.py           ← déduplication concurrents par website
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── CompanyCard.tsx
│   │   │   ├── CompetitorGrid.tsx
│   │   │   ├── CompetitorMap.tsx
│   │   │   └── PricingSignalFeed.tsx
│   │   ├── pages/
│   │   │   └── index.tsx      ← URL input + résultats
│   │   └── types/             ← mirrors des types Pydantic backend
│   └── package.json
└── cache/                     ← JSON cache local (gitignored)
│
└── Learning (pour tous les documents explicatifs que je te demande)
```

Et au niveau du repo (hors `radar/`) :

```
RADAR/
├── docs/
│   └── design-system/         ← specs markdown (principes, tokens, components, motion, voice, iconography, moodboard)
└── radar/frontend/src/design-system/
    ├── tokens.ts              ← source of truth des tokens (TypeScript)
    └── tailwind.preset.ts     ← preset Tailwind consommant tokens.ts
```

---

## 🔑 Variables d'environnement

```bash
# backend/.env (ne jamais commiter)
LINKUP_API_KEY=...
ANTHROPIC_API_KEY=...
NOMINATIM_USER_AGENT=radar-hackathon   # requis par Nominatim ToS

# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 📦 Stack & Versions

| Couche | Techno | Notes |
|---|---|---|
| Backend | Python 3.11+, FastAPI, Pydantic v2 | Pas de SQLAlchemy — JSON files pour le cache |
| LLM extraction | `claude-sonnet-4-20250514` | **Ne pas utiliser d'autres model strings** |
| Search | Linkup API | Voir section endpoints ci-dessous |
| Frontend | React 18, Tailwind CSS, TypeScript | Pas de Next.js SSR nécessaire — Vite suffit |
| Carte | Leaflet.js (react-leaflet) | Pas Mapbox — pas de clé API à gérer |
| Geocoding | Nominatim (gratuit) | PAS Google Maps — voir `utils/geocoding.py` |
| Deploy | Vercel (frontend) + Railway/Render (backend) | |

---

## 🔌 Linkup API — Patterns à utiliser

### Endpoints et quand les utiliser

```python
# Phase 1 — profil rapide
linkup.search(query="...", depth="standard")

# Phase 1 — funding ground truth
linkup.fetch(url="https://crunchbase.com/organization/...", render_js=True)

# Phase 2 — découverte large
linkup.search(query="...", depth="deep")

# Phase 3 — pricing exact
linkup.fetch(url="https://competitor.com/pricing", render_js=True)

# Phase 3 — signaux récents
linkup.search(query="...", depth="standard", from_date="2024-11-01")

# Phase 3 — enrichissement parallèle
linkup.tasks(requests=[...])  # batch async natif

# Mode Deep Dive (optionnel, beta)
linkup.research(query="...")
```

### Règle critique sur les coordonnées GPS
**Ne JAMAIS demander des coordonnées GPS à Linkup.** Linkup est un LLM — il inventerait des coords plausibles mais fausses. Workflow correct :
1. Linkup retourne `city` + `country`
2. `utils/geocoding.py` résout via Nominatim
3. Les coords sont stockées dans `CompanyProfile.coordinates`

### Fallback pattern obligatoire dans `linkup_client.py`

```python
async def fetch_pricing(url: str) -> str:
    try:
        return await linkup.fetch(url=url, render_js=True)
    except (CloudflareError, FetchError):
        # Fallback: recherche textuelle
        company = extract_domain(url)
        return await linkup.search(
            query=f"{company} pricing plans 2025",
            depth="standard"
        )
```

---

## 🧱 Modèles Pydantic — Conventions

### DataPoint : pattern de base pour chaque champ sourcé

```python
class DataPoint(BaseModel):
    value: Optional[str | int | float] = None
    confidence: Literal["high", "medium", "low"]
    source_url: Optional[str] = None
    extracted_at: str  # ISO datetime — datetime.utcnow().isoformat()
```

**Règle** : tout champ provenant de Linkup ou Claude doit être un `DataPoint`. Les champs structurels (name, website) peuvent être `str` direct.

### Ne pas modifier les modèles sans vérifier l'impact frontend

Les types TypeScript dans `frontend/src/types/` sont des mirrors manuels des modèles Pydantic. Si tu modifies un modèle Python, mets à jour le type TS correspondant dans la même tâche.

---

## 🚀 Commandes utiles

> **⚠️ Backend tourne dans un venv Python.** Toujours rappeler à l'utilisateur d'activer le venv ET d'être dans `RADAR/radar/backend/` avant toute commande Python ou `braintrust`.
>
> Setup terminal type pour ce projet :
> ```bash
> cd /Users/paul.pietra/Dev/GATRA/RADAR/radar/backend
> source .venv/bin/activate
> export $(grep -v '^#' .env | xargs)   # charge LINKUP/ANTHROPIC/BRAINTRUST keys
> ```
> Le CLI s'appelle `braintrust` (pas `bt`). Sans venv activé → `command not found`.

```bash
# Backend
cd RADAR/radar/backend
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Tester un pipeline complet en CLI (venv activé)
python -m pipeline.understand "doctolib.fr"
python -m pipeline.discover "doctolib.fr"
python -m pipeline.enrich '["livi.fr", "qare.fr", "medadom.com"]'

# Eval Braintrust (venv activé + BRAINTRUST_API_KEY exporté)
braintrust eval evals/eval_understand.py
braintrust eval evals/eval_discover.py
braintrust eval evals/eval_enrich.py

# Frontend
cd RADAR/radar/frontend
npm install
npm run dev   # port 3000

# Vider le cache
rm -rf cache/*.json
```

---

## ⚡ Règles de développement (hackathon mode)

### DO
- **Ship d'abord** — une feature qui marche à 80% livrée vaut mieux qu'une feature parfaite non livrée
- **Cache agressif** — clé `{company_domain}_{YYYY-MM-DD}` sur toutes les réponses Linkup
- **Async partout** côté backend — `async def` + `httpx.AsyncClient`
- **Types explicites** — Pydantic v2 pour tout output de pipeline
- **Confidence scores** — chaque `DataPoint` doit avoir un niveau de confiance honnête (ne pas mettre `high` par défaut)
- **Logs structurés** — `logger.info("phase=UNDERSTAND company=doctolib.fr status=ok duration=12.3s")`

### DON'T
- ❌ Ne pas halluciner des données si Linkup retourne vide → retourner `DataPoint(value=None, confidence="low")`
- ❌ Ne pas faire de calls Linkup séquentiels là où `/tasks` est disponible
- ❌ Ne pas mettre de coordonnées GPS hardcodées dans le code
- ❌ Ne pas bypasser le cache pour les runs de démo — les boîtes pré-computées doivent retourner instantanément
- ❌ Ne pas modifier `analysis_version` dans CompetitorProfile — elle reste `"3.0"` pour ce sprint

---

## 🎪 Boîtes pré-computées pour la démo

Ces 5 analyses doivent être dans le cache avant la démo live :

| Startup | Domaine | Secteur |
|---|---|---|
| Doctolib | doctolib.fr | Santé numérique |
| Notion | notion.so | Productivity SaaS |
| Slite | slite.com | Knowledge management |
| Alan | alan.com | Insurtech santé |
| Pennylane | pennylane.eu | Finance SaaS |

Commande de pré-compute :
```bash
python scripts/precompute_demo.py  # à créer en semaine 3
```

---

## 🔴 Points de vigilance pour Claude Code

1. **`/research` endpoint Linkup est en beta** — toujours l'entourer d'un try/except large et le traiter comme optionnel, jamais sur le chemin critique
2. **Déduplication des concurrents** — se fait par `website` (domaine normalisé), pas par `name` (variantes orthographiques)
3. **Coût Linkup** — ~0.60€ par analyse complète. Ne jamais lancer un pipeline complet en boucle pour débugger — utiliser les mocks dans `tests/fixtures/`
4. **CORS** — le backend FastAPI doit autoriser `localhost:3000` en dev et le domaine Vercel en prod
5. **Rate limiting Nominatim** — 1 req/s max, ajouter `asyncio.sleep(1)` entre les calls dans `geocoding.py`

---

## 🎨 Design System (Intelligence Ops)

RADAR a un design system formel — Palantir corporate × Perplexity transparency. Audience cible : VCs et corporate strategy. Toute UI doit s'y conformer.

### Structure hybride

- **Specs lisibles** : `RADAR/docs/design-system/` (markdown — principes, visual language, tokens, components, motion, voice, iconography, moodboard)
- **Source of truth code** : `RADAR/radar/frontend/src/design-system/tokens.ts` (constantes TS)
- **Preset Tailwind** : `RADAR/radar/frontend/src/design-system/tailwind.preset.ts` (consomme tokens.ts, exposé à Tailwind via `tailwind.config.ts`)

### Règles non négociables

1. **Pas de valeur hard-codée** dans les composants (couleurs, espacements, fontes, durées). Toujours via `tokens.ts` ou classes Tailwind générées par le preset.
2. **Pas de second système** — pas de Material UI, pas de shadcn copié-collé tel quel. Si un primitive est nécessaire, l'ajouter au design system (docs + code) avant de l'utiliser.
3. **Dark only** — pas de light mode v0. Pas de toggle.
4. **Mono pour data, sans pour prose** — JetBrains Mono pour IDs/URLs/données, Inter pour prose/headings.
5. **Motion fonctionnel uniquement** — pas d'animations décoratives. Voir `04_motion.md`.

### Composants disponibles

Voir `RADAR/docs/design-system/03_components.md` pour la liste complète et leurs specs. Avant de créer un nouveau composant, vérifier qu'un existant ne couvre pas le besoin.

### Quand modifier le design system

- Nouveau token (couleur, espacement, etc.) → update `tokens.ts` ET `02_tokens.md` dans la même commit.
- Nouveau composant → ajouter spec à `03_components.md` ET implémenter dans `src/components/` consommant les tokens.
- Changement de visuel → vérifier l'alignment avec `01_visual_language.md` et le 10-second test (voir doc).

---

## 📋 Format des réponses attendu de Claude Code

Pour chaque tâche :
1. **Confirm** : 1 phrase de compréhension de la tâche
2. **Plan** : liste des fichiers touchés
3. **Code** : diff minimal (pas de fichiers entiers si pas nécessaire)
4. **Risques** : ce qui pourrait casser, edge cases identifiés
5. **Test rapide** : la commande pour valider que ça marche

---

*CLAUDE.md v1.0 — Radar — Hackathon Linkup Mai 2026*