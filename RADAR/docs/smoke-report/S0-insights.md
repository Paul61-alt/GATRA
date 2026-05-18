# S0 Smoke Test — Insights & Decision Log

_Run date: 2026-05-17 | Domains: linear.app, pennylane.com, mistral.ai, cal.com_

---

## 1. Latency Breakdown

### Per-phase durations (seconds)

| Domain | understand | discover | enrich | transform | **Total** |
|---|---|---|---|---|---|
| linear.app | 12.0 | 107.2 | 17.4 | ~0 | **136.6** |
| pennylane.com | 11.0 | 78.0 | 21.6 | ~0 | **110.6** |
| mistral.ai | 45.0 | 132.1 | 16.5 | ~0 | **193.6** |
| cal.com | 9.6 | 59.4 | 22.7 | ~0 | **91.7** |
| **Avg** | **19.4** | **94.2** | **19.6** | **~0** | **~133s** |

### Takeaway

- **Discover owns the problem.** It consumes 72–85% of total wall time across all domains.
- Under favourable conditions (cal.com), the chain barely meets 90s. Under adversarial ones (mistral.ai), it hits ~194s — 2× the target.
- understand and enrich are well-behaved (~10-45s and ~17-23s respectively). transform is negligible.
- **The <90s target is not achievable without architectural change to discover.** See §4 for options.

---

## 2. Per-Smoke DoD Status

| Test | Phase | Result | DoD criterion | Verdict |
|---|---|---|---|---|
| S0.1 | understand | name, hq, coords, funding_stage, markets all returned | correct fields, no crash | **PASS** |
| S0.1 | understand | duration=36.4s (smoke run) | <20s | **WARN** |
| S0.2 | discover (CLI) | count=10 | count≥15 | **WARN** |
| S0.2 | discover (CLI) | all name+website filled, no dupes, plausible competitors | data quality | **PASS** |
| S0.3 | enrich | 3/3 hqCoords, pricing.tiers with source_url, 1-5 recent_signals | fields populated | **PASS** |
| S0.3 | enrich | funding_stage=None | funding carried through | **WARN** (stub artefact, not real bug) |
| S0.3 | enrich | duration=12s | <30s | **PASS** |
| S0.4 | full chain (FastAPI) | RadarOutput full schema returned, competitors=15, all hqCoords | schema valid, count=15 | **PASS** |
| S0.4 | full chain (FastAPI) | query.durationMs=0 | durationMs set | **FAIL** (transform bug) |
| S0.4 | full chain (FastAPI) | total duration=125s | <90s | **WARN** |
| S0.4 | full chain (FastAPI) | subject.hq="New York City" vs S0.1 "San Francisco" | deterministic hq | **WARN** |

---

## 3. Bugs Found

| # | Bug | Impact | Fix effort |
|---|---|---|---|
| B1 | `query.durationMs` always 0 in transform.py | Wrong timing in API output; misleading for monitoring | XS — set field from pipeline start/end timestamps |
| B2 | understand HQ non-deterministic across runs (NYC vs SF for linear.app) | Map center drift; potential competitor dedup miss if hq used as key | S — add system prompt constraint or post-process normalise to canonical city; root cause is Linkup returning variable context |
| B3 | CLI discover returns 10 instead of 15 | Smoke tests via CLI appear to fail count DoD; misleading for CI | XS — document CLI limitation or enrich stub profile in CLI entrypoint |
| B4 | enrich does not independently verify funding_stage | If discover passes None, enrich silently propagates it | S — add a targeted Linkup call for funding in enrich phase, or flag missing fields explicitly |

---

## 4. Decisions Needed

### D1 — Latency target: <90s is unreachable as-is

**Question:** What is the realistic SLA for the full pipeline?

| Option | Description | Tradeoff |
|---|---|---|
| (a) Relax target to <180s | No code change needed | Poor UX for live demo; 194s for mistral.ai still violates |
| (b) Parallelize understand + discover | Both phases can start concurrently; discover uses understand output but discover can also use domain directly | Saves ~19s avg; discover still 59-132s; total still 80-175s |
| (c) Pre-cache demo domains | Warm cache for linear/notion/etc. before demo | Demo-only fix; production still slow |
| (d) Streaming / progressive UI | Return understand result immediately, stream discover + enrich as they resolve | Total latency unchanged but UX perception improved significantly |
| (e) b + d combined | Parallelize phases AND stream results | Best UX; moderate implementation complexity |

**Recommendation:** Ship (d) first (streaming skeleton), then (b). Set backlog target to <150s for now. (c) as tactical demo safety net. Do not close latency work until discover is understood: Linkup call count and timeout behaviour need profiling.

---

### D2 — CLI discover count (10 vs 15)

**Question:** Is the CLI entrypoint a supported path or internal tooling only?

| Option | Description |
|---|---|
| (a) Document as known limitation | CLI uses stub profile → weaker Linkup query → fewer results |
| (b) Enrich stub in CLI | Pass domain through understand before discover even in CLI mode |

**Recommendation:** (b) if CLI is used in CI/evals. (a) if CLI is dev-only. Decision owner: whoever writes S1 evals.

---

### D3 — HQ non-determinism

**Question:** Should `subject.hq` be treated as stable or volatile?

**Impact areas:** map center pin, competitor dedup logic, any hq-based filtering.

| Option | Description |
|---|---|
| (a) Post-process normalise | After LLM extraction, resolve city to canonical name via geocoding (already have lat/lng — reverse geocode for canonical city) |
| (b) Structured extraction with enum constraint | Pass allowed cities list or stricter prompt to bound output variance |
| (c) Accept variance, don't use hq as key | Use domain as dedup key everywhere; treat hq as display-only |

**Recommendation:** (c) immediately (use domain as canonical key). (a) as polish pass before public demo. (b) adds latency and fragility.

---

### D4 — durationMs=0 (B1)

**Question:** Fix now or defer?

**Recommendation:** Fix now. XS effort, and wrong timing data will pollute any future performance monitoring or alerting.

---

### D5 — Enrich not re-fetching funding_stage (B4)

**Question:** Should enrich be a pure pass-through for fields already set, or should it verify/enrich all fields independently?

| Option | Description |
|---|---|
| (a) Enrich only fills gaps | If discover returns funding_stage, trust it |
| (b) Enrich always re-fetches funding | Higher latency, higher Linkup cost, higher accuracy |
| (c) Flag missing fields | If funding_stage is None after enrich, surface it as a data-quality warning in the output |

**Recommendation:** (a) + (c). Enrich should not duplicate discover work. But missing critical fields after enrich should be visible in output (e.g. `data_quality.missing_fields[]`).

---

## 5. Next Steps (priority order)

| Priority | Action | Owner | Effort | Blocks |
|---|---|---|---|---|
| P0 | ~~Fix B1: set `query.durationMs` in transform.py~~ **DONE** (`transform.py` fixed 2026-05-17) | eng | XS | monitoring, S0.4 FAIL |
| P1 | Update backlog latency target from <90s to <150s | PM | XS | D1 |
| P2 | Profile discover: count Linkup calls, measure per-call latency, identify parallelisation opportunities | eng | S | D1 option (b) |
| P3 | Wire frontend to existing `/scan/stream` SSE endpoint (backend already implemented in `main.py:164-216`) | eng | M | D1 option (d) |
| P4 | Fix B3: document or fix CLI stub — decide if CLI is CI path | PM+eng | XS | S1 evals |
| P5 | Fix D3: use domain as dedup/identity key everywhere, not hq | eng | XS | B2 map drift |
| P6 | Wire S0.5: end-to-end regression test covering all 4 domains via FastAPI (not CLI) | eng | S | S1 milestone gate |
| P7 | Build S1.1: discover quality eval — measure competitor recall vs ground truth set | eng | M | S1 milestone |
