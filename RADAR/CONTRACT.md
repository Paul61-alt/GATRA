# RADAR — Backend ↔ Frontend Contract

> **For the frontend developer.** This document is the authoritative reference for what the backend sends, what's real, and what's a placeholder. Read it before wiring any UI component to data.

---

## TL;DR

- Use **`POST /scan/stream`** (SSE) for the main UI — you get live progress + final result
- Use **`POST /scan`** if you just want the JSON synchronously
- The final payload shape is **`RadarOutput`** (camelCase throughout)
- Interactive API explorer: `http://localhost:8000/docs`
- Raw OpenAPI JSON: `http://localhost:8000/openapi.json`

---

## Endpoints

| Route | Method | Returns | Auth |
|-------|--------|---------|------|
| `POST /scan/discover` | JSON | `DiscoverResult` (candidates list) | none |
| `POST /scan/enrich` | SSE stream | progress events → `RadarOutput` | none |
| `POST /scan/stream` | SSE stream | progress events → `RadarOutput` (full pipeline) | none |
| `POST /scan` | JSON | `RadarOutput` (full pipeline) | none |
| `POST /analyze` | JSON | `PipelineRun` (internal, snake_case) | none — do not use in UI |
| `GET /health` | JSON | `{ "status": "ok" }` | none |

**Rate limit:** 3 req/min on all POST endpoints. Returns `429` if exceeded.

**Concurrency cap:** backend runs at most 2 pipelines in parallel. A 3rd request blocks until one finishes.

**HITL flow (recommended):** `POST /scan/discover` → VC selects candidates → `POST /scan/enrich`
**Legacy full-pipeline flow:** `POST /scan/stream` or `POST /scan` — runs everything in one shot.

**Request body:**
- `/scan/discover`, `/scan`, `/scan/stream`, `/analyze`: `{ "url": "notion.so" }` — accepts bare domain, `https://...`, or any URL
- `/scan/enrich`: see EnrichRequest below

---

## HITL Flow — `/scan/discover` + `/scan/enrich`

### `POST /scan/discover`

Runs UNDERSTAND + DISCOVER only (~15s). Returns lightweight candidate list for VC to select.

**Request:**
```json
{ "url": "notion.so" }
```

**Response — `DiscoverResult`:**
```json
{
  "runId": "550e8400-e29b-41d4-a716-446655440000",
  "companyName": "Notion",
  "companyDomain": "notion.so",
  "companyTagline": "All-in-one workspace for notes, docs, and collaboration",
  "candidates": [
    { "name": "Coda", "domain": "coda.io", "tagline": "All-in-one doc for teams" },
    { "name": "Craft", "domain": "craft.do", "tagline": "Beautiful docs built for teams" }
  ],
  "scannedAt": "2026-05-26T10:00:00Z",
  "sourcesCount": 18
}
```

Candidates are ordered by competitive threat (best-effort — may be unordered if scoring fails).
`runId` is valid for **2 hours** — pass it to `/scan/enrich` before expiry.

### `POST /scan/enrich`

Runs ENRICH + SYNTHESIZE on VC-selected candidates. Returns SSE stream → `RadarOutput`.

**Request — `EnrichRequest`:**
```json
{
  "runId": "550e8400-e29b-41d4-a716-446655440000",
  "selected": ["coda.io", "craft.do", "notion.so"]
}
```

`selected` = bare domains VC checked in the UI. Must be a non-empty subset of `candidates[].domain` from the prior `/scan/discover` response.

**SSE stream:** same format as `/scan/stream` but only ENRICH + SYNTHESIZE phases.

```json
{ "phase": "ENRICH",     "status": "start" }
{ "phase": "ENRICH",     "status": "progress", "done": 1, "total": 3 }
{ "phase": "ENRICH",     "status": "ok", "count": 3 }
{ "phase": "SYNTHESIZE", "status": "start" }
{ "phase": "SYNTHESIZE", "status": "ok", "count": 3 }
```

Final event: `{ "result": { /* RadarOutput — same shape as /scan/stream */ } }`

**Errors:**
- `404` — `runId` not found or expired (2h TTL). Re-run `/scan/discover`.
- `422` — `selected` list is empty.

---

---

## SSE Stream — `/scan/stream`

Connection opens immediately. Backend sends:

### 1. Connection ack (not a data event)
```
: connected
```

### 2. Phase progress events
```json
{ "phase": "UNDERSTAND", "status": "start" }
{ "phase": "UNDERSTAND", "status": "ok", "name": "Notion" }

{ "phase": "DISCOVER",   "status": "start" }
{ "phase": "DISCOVER",   "status": "ok", "count": 8 }

{ "phase": "ENRICH",     "status": "start" }
{ "phase": "ENRICH",     "status": "progress", "done": 3, "total": 8 }
{ "phase": "ENRICH",     "status": "polling", "attempt": 1 }
{ "phase": "ENRICH",     "status": "batch_complete", "count": 8 }
{ "phase": "ENRICH",     "status": "ok", "count": 8 }

{ "phase": "SYNTHESIZE", "status": "start" }
{ "phase": "SYNTHESIZE", "status": "ok", "count": 9 }
```

### 3. Keepalive (every 15s during long phases)
```
: keepalive
```

### 4. Final result
```json
{ "result": { /* full RadarOutput object — see below */ } }
```

### 5. Error (replaces result on failure)
```json
{ "error": "Linkup API timeout after 30s" }
```

**Parsing SSE in JS:**
```ts
const source = new EventSource('/scan/stream', { ... }); // EventSource doesn't do POST
// Use fetch + ReadableStream instead — see useSseScan.ts
```

---

## `RadarOutput` — Full Shape

All field names are **camelCase** in the JSON. The backend Pydantic model uses `alias_generator=to_camel`, so the mapping is deterministic.

```ts
interface RadarOutput {
  query:        ScanQuery
  subject:      RadarCompany          // the company being analyzed
  competitors:  RadarCompany[]        // 0–15 competitors, sorted by threat desc
  features:     RadarFeature[]        // ⚠️ ALWAYS [] — see stubs below
  capabilities: Record<string, CapValue[]>  // ⚠️ ALWAYS {} — see stubs below
  pricing:      Record<string, RadarPricingTier[]>  // keyed by company.id
  funding:      Record<string, RadarFundingEvent[]> // keyed by company.id
  radar:        RadarConfig
}
```

---

### `ScanQuery`

```ts
interface ScanQuery {
  url:             string   // raw domain passed to /scan
  name:            string   // resolved company name
  scannedAt:       string   // ISO 8601 timestamp
  durationMs:      number   // pipeline wall time in milliseconds
  sourcesScanned:  number   // unique URLs crawled across all phases
}
```

---

### `RadarCompany` (subject + each competitor)

```ts
interface RadarCompany {
  id:             string              // slug, e.g. "notion", "coda_io"
  name:           string              // "Notion"
  domain:         string              // "notion.so"
  tagline:        string              // one-liner / summary
  category:       string              // primary market label, e.g. "Productivity"
  subCategory:    string              // positioning string
  hq:             string              // "San Francisco, United States"
  hqCoords:       [number, number]    // [lat, lng] — [0, 0] if unknown
  offices?:       string[]            // usually just [city] of HQ
  founded?:       number | null       // founding year, e.g. 2016
  employees?:     number | null       // headcount integer, e.g. 500
  employeeGrowth: number              // ⚠️ ALWAYS 0.0 — see stubs
  funding?:       FundingInfo | null
  investors?:     string[]            // ⚠️ ALWAYS [] for all companies — see stubs
  pricing?:       PricingSummary | null
  arr?:           number | null       // ⚠️ ALWAYS null — see stubs
  customers?:     number | null       // ⚠️ ALWAYS null — see stubs
  avgContract?:   number | null       // ⚠️ ALWAYS null — see stubs
  notable?:       string[]            // up to 5 growth signals / recent news headlines
  isSubject?:     boolean             // true only on subject
  similarity?:    number | null       // ⚠️ ALWAYS 0.5 on competitors — see stubs
  threat?:        "high"|"medium"|"low"|null  // ⚠️ ALWAYS "medium" on competitors — see stubs
}
```

---

### `FundingInfo`

```ts
interface FundingInfo {
  total:       number   // total raised in EUR (float)
  lastRound:   string   // e.g. "Series B"
  lastRoundAt: string   // "YYYY-MM" format, e.g. "2022-06"
}
```

---

### `PricingSummary`

```ts
interface PricingSummary {
  model:    string   // e.g. "Freemium", "Subscription", "Custom"
  startsAt: number   // entry price in USD (0 if free or unknown)
  mention:  string   // human label, e.g. "Free tier available", "Contact sales"
}
```

> **Note:** subject company always has `{ model: "Custom", startsAt: 0, mention: "Contact sales" }` — subject pricing tiers are not extracted yet.

---

### `RadarPricingTier`

Keyed in `RadarOutput.pricing` by company `id`. Each tier:

```ts
interface RadarPricingTier {
  name:      string    // "Free", "Pro", "Enterprise"
  price:     string    // "$0", "$49", "Custom"
  per:       string    // "month", "year", "contact"
  features?: string[]  // up to 6 feature strings
}
```

Example:
```json
{
  "pricing": {
    "coda_io": [
      { "name": "Free",       "price": "$0",   "per": "month", "features": ["5 docs", "Unlimited viewers"] },
      { "name": "Pro",        "price": "$10",  "per": "month", "features": ["Unlimited docs", "Custom domains"] },
      { "name": "Team",       "price": "$30",  "per": "month", "features": ["SSO", "Admin panel"] },
      { "name": "Enterprise", "price": "Custom","per": "contact","features": [] }
    ],
    "notion": []
  }
}
```

---

### `RadarFundingEvent`

Keyed in `RadarOutput.funding` by company `id`. Subject has events; **competitors always have `[]`**.

```ts
interface RadarFundingEvent {
  y:     number   // year, e.g. 2021
  q:     number   // quarter 1–4
  amt:   number   // amount in M€, e.g. 275.0
  round: string   // "Series C", "Seed", etc.
}
```

---

### `RadarConfig`

```ts
interface RadarConfig {
  axes:   string[]                      // 6 axis labels (fixed order)
  scores: Record<string, number[]>      // entity id → [6 scores 0–100]
  defs:   Record<string, string>        // axis → description
}
```

Fixed axes (always in this order):
```
["Breadth", "Depth", "Global", "Developer", "Pricing", "Trust"]
```

Example:
```json
{
  "axes": ["Breadth", "Depth", "Global", "Developer", "Pricing", "Trust"],
  "scores": {
    "notion":  [72, 65, 80, 45, 70, 68],
    "coda_io": [68, 70, 40, 55, 65, 55]
  },
  "defs": {
    "Breadth":   "Breadth of product surface (modules, use-cases)",
    "Depth":     "Depth within core payment workflows",
    "Global":    "Geographic and currency coverage",
    "Developer": "API quality, docs, embedded SDKs",
    "Pricing":   "Price-competitiveness for SMB/mid-market",
    "Trust":     "Compliance, brand and customer logos"
  }
}
```

---

## `window.RADAR_DATA` (static HTML mode)

When using the exported `data.js` file (not the API), the frontend reads:

```js
window.RADAR_DATA          // full RadarOutput object
window.RADAR_DATA.allCompanies  // [subject, ...competitors] sorted by similarity desc
```

---

## ⚠️ Known Stubs — Read Before Wiring UI

These fields are **not yet computed**. Build placeholder UI for them — do not block on real data.

| Field | Always returns | Reason | ETA |
|-------|---------------|--------|-----|
| `RadarOutput.features` | `[]` | Feature matrix not extracted | Post-demo |
| `RadarOutput.capabilities` | `{}` (empty dict) | Depends on features | Post-demo |
| `RadarCompany.similarity` | `0.5` on all competitors | Embedding similarity not impl. | Post-demo |
| `RadarCompany.threat` | `"medium"` on all competitors | Heuristics planned | Post-demo |
| `RadarCompany.arr` | `null` | No data source | TBD |
| `RadarCompany.customers` | `null` | No data source | TBD |
| `RadarCompany.avgContract` | `null` | No data source | TBD |
| `RadarCompany.employeeGrowth` | `0.0` | No time-series data | TBD |
| `RadarCompany.investors` | `[]` | Mapped but not populated | Sprint+1 |
| `funding[competitor_id]` | `[]` | No round history for competitors | TBD |
| `pricing[subject_id]` | `[]` | Subject pricing not extracted | Sprint+1 |

**What this means in practice:**
- Radar chart → works ✅ (real heuristic scores)
- Pricing comparison table → works for competitors ✅, empty for subject ⚠️
- Funding timeline → works for subject ✅, no competitor events ⚠️
- Feature matrix (`features` × `capabilities`) → render skeleton/coming-soon state
- Similarity badge → render as `—` or omit
- Threat badge → hardcoded "medium", you can still render it but don't trust the value

---

## Types Alignment

The TypeScript types in `frontend/src/types/index.ts` mirror this contract.

> ⚠️ They are **hand-maintained**. If you see a field in this document that doesn't match the TS interface, the TS file is stale — refer to this document and to `http://localhost:8000/openapi.json` as ground truth.

**Mapping to check:**
- Backend `snake_case` field → frontend `camelCase` key (automatic via Pydantic alias)
- Exception: `FundingEvent.round_name` in Python → JSON key `"round"` (aliased to avoid Python builtin conflict)

---

## Minimal End-to-End Example

```ts
const res = await fetch('http://localhost:8000/scan', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ url: 'notion.so' })
});
const data: RadarOutput = await res.json();

console.log(data.subject.name);           // "Notion"
console.log(data.competitors.length);     // e.g. 8
console.log(data.radar.scores['notion']); // [72, 65, 80, 45, 70, 68]
console.log(data.pricing['coda_io']);     // [{name: "Free", price: "$0", ...}]
console.log(data.features);              // [] — stub
```

---

## Dev Checklist for Frontend

- [ ] Consume `/scan/stream` via `useSseScan.ts` hook (already implemented)
- [ ] Display 4 phase states: UNDERSTAND → DISCOVER → ENRICH → SYNTHESIZE
- [ ] Handle `{ "error": "..." }` SSE event → show error state
- [ ] Radar chart: use `radar.scores[company.id]` — 6 values, 0–100
- [ ] Pricing table: skip subject entry (always `[]`), show tiers for competitors
- [ ] Features matrix: render "coming soon" or loading skeleton — data is `[]`
- [ ] `hqCoords` `[0,0]` = unknown location — hide map pin, don't render at null island
- [ ] `threat` and `similarity` = placeholder values — use with care in UI copy

---

*Contract last updated: 2026-05-25 — matches backend `analysis_version: "4.0"`*
