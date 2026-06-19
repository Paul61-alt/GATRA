# RADAR — Architecture & Code Audit
**Date:** 2026-05-26  
**Scope:** Full codebase review, backend architecture, data flow, integrations, quality  
**Format:** Consultant-style — findings, rationale, recommendations by priority

---

## Executive Summary

RADAR is a solid hackathon-stage project. Core pipeline works end-to-end. Type safety, async architecture, and budget controls are genuinely well done for a non-CS background. 

**The problems are concentrated in two areas:**
1. **Placeholder values** — 40% of the output is hardcoded stubs (scores, threat levels, similarity, features). The pipeline runs, but the data it returns is fake.
2. **Structural tech debt** — code duplication, fragile JSON parsing, missing tests. These don't break the demo but create rework drag as the project grows.

**Health scores by category:**

| Area | Score | Trend |
|---|---|---|
| Architecture (separation of concerns) | 8/10 | ✅ Solid |
| Type safety & contracts | 8/10 | ✅ Solid |
| API integrations (Linkup, Claude) | 8/10 | ✅ Solid |
| Documentation | 8/10 | ✅ Solid |
| Code quality (duplication, fragility) | 6/10 | ⚠️ Needs work |
| Backend completeness | 6/10 | ⚠️ Phase 4 placeholder |
| Performance | 5/10 | ⚠️ Discover 5× over target |
| Testing | 4/10 | ❌ No unit tests |
| Frontend | 4/10 | ❌ Two implementations, mismatch |
| Deployment readiness | 2/10 | ❌ Zero setup |

---

## Part 1 — Architecture

### What's Good

**Layered architecture is correct.** Pipeline phases are cleanly separated:

```
main.py (routing + orchestration)
    ↓
pipeline/understand.py, discover.py, enrich.py, synthesize.py, transform.py
    ↓
clients/linkup_client.py, claude_client.py
    ↓
models/company.py, competitor.py, pipeline.py, radar_output.py
    ↓
utils/cache.py, dedup.py, geocoding.py
```

Each layer calls only the layer below it. No model talks to a client directly. No route calls `linkup_client` directly. This is the right pattern — it means you can swap Linkup for another provider by changing `clients/linkup_client.py` without touching pipeline logic.

**Rationale:** The #1 cause of unmaintainable apps is layers calling each other arbitrarily. You avoided it. This is not a given for autodidact projects — most junior devs skip this and pay for it later.

**Async-first is correct.** All I/O (Linkup, Claude, Nominatim, file reads) uses `async/await`. This means the server can handle 2 concurrent pipelines without blocking. The semaphore (`asyncio.Semaphore(2)`) correctly limits concurrency without rejecting requests — it queues them.

**Pydantic v2 throughout is correct.** Every inter-layer interface is a typed model. You can't pass a dict where a `CompanyProfile` is expected. This catches bugs at the boundary, not in production.

**DataPoint pattern is sophisticated.** Wrapping every sourced field in:
```python
class DataPoint(BaseModel):
    value: Optional[str | int | float]
    confidence: Literal["high", "medium", "low"]
    source_url: Optional[str]
    evidence: Optional[str]
    extracted_at: str
```
…means provenance is traceable per field. That's a design decision most senior engineers wouldn't bother with at hackathon stage. Keep it.

---

### What Needs Work

#### Issue 1 — `main.py` mixes routing, orchestration, and config (MEDIUM)

`main.py` currently does:
- FastAPI route definitions
- Domain normalization logic (`_normalize_domain`)
- Pipeline orchestration (`run_pipeline`, cache reads/writes)
- App startup (`lifespan`, client initialization)
- SSE stream management

**Rationale for fixing:** As the app grows, this file becomes the "god file" — the one you're always editing, where bugs hide. Routing should just dispatch; business logic should live in services.

**Recommended split:**
```
backend/
├── main.py              # FastAPI app init + lifespan only
├── routes/
│   ├── scan.py          # POST /scan, /scan/stream, /scan/discover, /scan/enrich
│   └── health.py        # GET /health
├── services/
│   └── scan_service.py  # run_pipeline, cache logic, SSE orchestration
├── pipeline/            # (keep as-is)
├── clients/             # (keep as-is)
├── models/              # (keep as-is)
└── utils/               # (keep as-is)
```

**Effort:** ~2h refactor. No logic changes, only file reorganization.

---

#### Issue 2 — Two `_normalize_domain` functions exist (LOW, but tells a story)

`main.py` has its own `_normalize_domain(url)`. `utils/dedup.py` also normalizes domains. They're not identical.

**Why this matters:** This is the classic symptom of "I needed this here so I wrote it here." Over time you get 3 versions of the same function, each slightly different, each causing subtle bugs. 

**Fix:** `utils/domain.py` → single `normalize_domain(url: str) -> str`. Import from both places. 10 min.

---

#### Issue 3 — `claude_client.py` has duplicate methods (MEDIUM)

`discover_competitors_fallback` is defined twice with different signatures (lines ~204 and ~340). `score_threats` is defined twice (lines ~303 and ~381).

**Why:** Likely a merge accident or iterative addition without cleanup. 

**Why it matters:** When you fix a bug in one, you don't fix it in the other. You'll hit this eventually.

**Fix:** Keep the most complete version of each, delete the other, update all call sites. ~30 min.

---

#### Issue 4 — JSON extraction is fragile (MEDIUM)

`claude_client.py` extracts JSON from Claude responses using:
```python
start = text.find("{")
end = text.rfind("}")
return json.loads(text[start:end+1])
```

**Problem:** Claude sometimes wraps JSON in markdown fences (` ```json ... ``` `). `text.find("{")` finds the `{` inside the fence, `text.rfind("}")` finds the closing `}`, but the `rfind` might land on a different object if Claude returned two JSON blocks.

**Better approach:**
```python
import re

def extract_json_from_text(text: str) -> dict:
    # Try markdown fence first
    fence_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if fence_match:
        return json.loads(fence_match.group(1))
    # Fall back to first complete JSON object
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError("No JSON found in response")
```

**Effort:** 30 min. Prevents silent parse failures.

---

## Part 2 — Pipeline & Data Quality

### The Placeholder Problem

This is the most important section. Run the pipeline today and you get:

| Field | Current Value | What it should be |
|---|---|---|
| Radar scores | `[50, 50, 50, 50, 50, 50]` for every company | Computed from real data |
| Threat level | `"medium"` for every competitor | Based on overlap analysis |
| Similarity | `0.5` for every competitor | Based on positioning analysis |
| Features matrix | `[]` (empty) | Feature comparison table |
| Capabilities | `{}` (empty) | Capabilities by company |
| Source tracking | `[]` (empty) | URLs that fed each field |
| Employee growth | `0.0` for all | Real % YoY |
| ARR, customers | `null` for all | From enrichment |

**Rationale:** A radar chart where every competitor scores 50/50/50 is not just incomplete — it actively misleads a VC. If you demo this, the first investor who looks at the numbers will catch it. This is the highest-priority fix before any presentation.

---

### Phase 4 (Synthesize) — Blocker

`synthesize.py` returns hardcoded `[50, 50, 50, 50, 50, 50]` for every company.

**What real scoring needs:** For each of the 6 axes (Breadth, Depth, Global, Developer, Pricing, Trust), you need heuristics that map data you already have onto a 0–100 score.

**Concrete implementation plan:**

```python
# Breadth: width of product scope
# Heuristic: count of unique features + number of target segments
def score_breadth(profile: CompetitorProfile) -> float:
    feature_count = len(profile.key_differentiators)
    segment_diversity = 1 if profile.target_segment else 0
    return min(100, feature_count * 10 + segment_diversity * 20)

# Pricing: affordability + flexibility
# Heuristic: has free plan, price per tier, number of tiers
def score_pricing(profile: CompetitorProfile) -> float:
    if not profile.pricing:
        return 50
    score = 50
    if profile.pricing.free_plan:
        score += 20
    tier_count = len(profile.pricing.tiers)
    score += min(30, tier_count * 10)
    return min(100, score)

# Trust: brand signals, notable customers, press
def score_trust(profile: CompetitorProfile) -> float:
    score = 30  # baseline
    score += min(40, len(profile.notable_customers) * 8)
    score += min(20, len(profile.recent_signals) * 4)
    if profile.key_investors:
        score += 10
    return min(100, score)
```

**Effort:** 2–3h. You have all the data in `CompetitorProfile` already. The synthesis phase just needs to read it.

---

### Phase 3 (Enrich) — MAX_ENRICH cap leaves 10/15 competitors as empty stubs

**Current state:** `MAX_ENRICH=5` means only 5 of 15 discovered competitors get enriched. The other 10 have all fields as `null` or `[]`.

**Why this was done:** Budget control. Each `/research` job costs €1.50. 15 jobs = €22.50 per scan. Too expensive for a hackathon.

**Better approach:** Tiered enrichment.

```
TOP 5 (threat score > 70): Full /research job (€1.50 each = €7.50)
NEXT 5 (threat score 40–70): /search deep structured (€0.055 each = €0.28)
BOTTOM 5 (threat score < 40): Basic /fetch + Claude parse (€0.025 each = €0.13)

Total: ~€7.91 vs current ~€7.50 (same budget) but 15/15 enriched
```

This fills all 15 competitors with real data instead of 10 empty stubs. The bottom 5 have less detail, but they have something.

**Effort:** 3–4h. Requires refactoring `enrich.py` to dispatch by tier.

---

### Source Tracking — `source_urls` always empty

Every `CompanyProfile` and `CompetitorProfile` has `source_urls: List[str]` that always serializes as `[]`.

**Why this matters:** A VC memo without citations is not defensible. "Funding: €5M Series A" needs a source. Without it, it reads as hallucination.

**Root cause:** The Linkup response includes `sources` array per result, but the pipeline never routes them back to the model fields.

**Fix:** In each pipeline phase, collect `result.sources` from Linkup calls and attach to the profile's `source_urls`. 1–2h of plumbing.

---

## Part 3 — Performance

### Discover Phase: 107–132s vs 20s target

**Current pipeline:**
1. Build one query string
2. Call `linkup /search depth=deep` with that query
3. Linkup internally runs 5–10 sub-queries sequentially
4. Return combined result after 107–132s

**Why it's slow:** `/search depth=deep` is sequential inside Linkup. You can't parallelize Linkup's internal process.

**What you can control:**

**Option A — Run parallel standard searches (recommended)**
```python
# Instead of 1 deep search:
# Run 3 parallel standard searches with different query angles
queries = [
    f"{name} competitors alternative",
    f"{name} vs {market} tools",
    f"{market} {segment} software providers"
]
results = await asyncio.gather(*[
    linkup.search(q, depth="standard") for q in queries
])
# Merge + deduplicate results
# Cost: 3 × €0.006 = €0.018 vs €0.055 (cheaper + faster)
```

**Expected improvement:** Standard search is ~15–20s vs deep ~100s. 3 parallel = ~20s total.

**Option B — Use discover intermediate cache more aggressively**
Cache competitor lists by `{market_id}` cross-scan. Companies in the same market share many competitors. If you've scanned Notion and a new scan comes in for Coda, the discovery phase can start from cached Notion competitors.

**Effort for Option A:** 2h. High impact on demo feel.

---

## Part 4 — Testing

### Current State: No pytest, no unit tests

All testing is via Braintrust evals that hit the real Linkup API. Cost ~€0.65/run.

**Problem:** You can't run tests without spending money. This means:
- You won't test as often (it costs)
- You'll merge broken code because manual testing is expensive
- CI/CD is impossible without mocking

**What to add:**

**1. Unit tests for pure functions (free to run)**
```
tests/
├── test_dedup.py         # normalize_domain(), deduplicate_candidates()
├── test_transform.py     # pipeline_run_to_radar_output() with fixture
├── test_synthesize.py    # score_* functions once implemented
└── test_cache.py         # cache_get/set with tmp directory
```

**2. Integration tests with mocked Linkup/Claude**
```python
# tests/conftest.py
@pytest.fixture
def mock_linkup(mocker):
    return mocker.patch("clients.linkup_client.LinkupClient.search",
                        return_value=load_fixture("linkup_search_response.json"))
```

**Fixtures you already have:** `cache/*.json` files are real pipeline outputs. Reuse them as test fixtures.

**Effort:** 4h initial setup. Pays for itself in first avoided regression.

---

## Part 5 — Frontend Situation

### Two implementations, one unclear

| | frontend-prototype/ | radar/frontend/ (deleted in this branch) |
|---|---|---|
| Framework | React 18 standalone | Next.js (deleted?) |
| Screens | 9 complete screens | Unknown |
| Data binding | `window.RADAR_DATA` | — |
| Status | Works, not served | Deleted in branch |

**This is the clearest blocker for deployment.** Git shows the `radar/frontend/` directory as deleted (`D`) in the current branch. The prototype (`frontend-prototype/`) exists but is not a real build pipeline — it's a standalone HTML+JSX file, not deployable to Vercel.

**Decision needed before deployment:**
1. Resurrect `radar/frontend/` (Next.js) and wire it to the real API
2. OR convert `frontend-prototype/` into a proper Vite/Next.js project

**Recommendation:** Option 2. The prototype has 9 complete screens. Convert it to a Vite+React project (add `package.json`, split JSX into components, point `VITE_API_URL` at backend). Faster than rebuilding from scratch.

**Effort:** 1 day. Highest UX impact.

---

## Part 6 — Deployment

### Current state: Nothing deployed

No CI/CD, no cloud config, no pre-cache script. The app runs locally only.

**Minimum to demo:**

**Backend (Railway)**
```yaml
# railway.json
{
  "build": { "builder": "NIXPACKS" },
  "deploy": {
    "startCommand": "uvicorn backend.main:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/health"
  }
}
```
Set env vars: `LINKUP_API_KEY`, `ANTHROPIC_API_KEY`, `NOMINATIM_USER_AGENT`, `FRONTEND_URL`.

**Frontend (Vercel)**
```
# Set VITE_API_URL=https://your-railway-app.railway.app
vercel --prod
```

**Pre-cache script (for demo reliability)**
```python
# scripts/precache_demo.py
DEMO_DOMAINS = ["linear.app", "pennylane.com", "mistral.ai", "cal.com", "notion.so"]
for domain in DEMO_DOMAINS:
    response = httpx.post("http://localhost:8000/scan", json={"url": domain})
    print(f"{domain}: {response.status_code}")
```
Run this 24h before demo. Demo scans return in <1s (cache hit).

**Effort:** 4h total. Without this, demo = hoping Linkup doesn't timeout in front of investors.

---

## Prioritized Action List

### Before any demo (blockers)

| Priority | Issue | File | Effort | Impact |
|---|---|---|---|---|
| P0 | Implement real synthesize scores | `pipeline/synthesize.py` | 2–3h | Radar chart shows real data |
| P0 | Fill source_urls tracking | `pipeline/understand.py`, `enrich.py` | 1–2h | Memo is defensible |
| P1 | Tiered enrichment (15/15 vs 5/15) | `pipeline/enrich.py` | 3–4h | No empty stubs |
| P1 | Fix JSON extraction fragility | `clients/claude_client.py` | 30 min | Fewer silent failures |
| P1 | Deploy backend + frontend | `railway.json`, Vercel | 4h | Can actually demo |
| P2 | Pre-cache demo domains | `scripts/precache_demo.py` | 1h | Demo loads in <1s |

### After demo (tech debt)

| Priority | Issue | File | Effort |
|---|---|---|---|
| P2 | Split main.py into routes/ + services/ | `main.py` | 2h |
| P2 | Fix Discover performance (parallel standard searches) | `pipeline/discover.py` | 2h |
| P2 | Remove duplicate methods in ClaudeClient | `clients/claude_client.py` | 30 min |
| P2 | Unify normalize_domain | `main.py`, `utils/dedup.py` | 10 min |
| P3 | Add pytest + mocked unit tests | `tests/` | 4h |
| P3 | Auto-generate TypeScript types from Pydantic | CI step | 2h |
| P3 | Circuit breaker for Linkup failures | `clients/linkup_client.py` | 1h |

---

## What You Should Learn From This

Three concepts explain most of the issues above:

**1. Separation of concerns** — every file should have one reason to change. `main.py` has 4. When you find yourself editing the same file for routing fixes, orchestration logic, and config changes, it's a signal to split.

**2. Test-driven thinking** — not necessarily TDD (write test first), but "how would I test this?" as a design check. If the answer is "I'd need to hit the real API", that's a sign to inject a dependency (mock-able client interface). Your clients are already injectable — you just need the tests.

**3. Placeholder discipline** — in software, placeholder values that look like real data are more dangerous than missing data. `null` makes it obvious something is missing. `50/50/50` radar scores look real and are wrong. Always return `null` or `{}` instead of fake values until the real implementation exists.

---

*Audit by Claude Code — based on full codebase read, May 2026*
