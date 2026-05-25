# RADAR — Frontend ↔ Backend Contract

> **Source of truth:** [`radar/backend/models/radar_output.py`](../radar/backend/models/radar_output.py)  
> **TypeScript types:** [`radar/frontend/src/types/index.ts`](../radar/frontend/src/types/index.ts)

---

## TL;DR

```
POST /scan/stream  →  SSE stream  →  final event: { result: RadarOutput }
```

The backend streams progress events in real time, then sends a final JSON payload.  
All keys in the JSON are **camelCase** (auto-converted from Python snake_case via Pydantic).

---

## 1. Endpoint

```
POST http://localhost:8000/scan/stream
Content-Type: application/json

{ "url": "stripe.com" }
```

**Rate limit:** 3 requests/minute per IP.

**CORS origins allowed:** `localhost:3000`, `localhost:5173`, `localhost:8080`, + `FRONTEND_URL` env var.

**Environment variable (frontend):**
```
VITE_API_URL=http://localhost:8000   # default if not set
```

---

## 2. SSE Stream Format

The response is a `text/event-stream`. Events arrive as:

```
: connected

: flush
data: { ...event JSON... }

: keepalive

: flush
data: { ...event JSON... }
```

- `: connected` — first byte, confirms stream is open (not a data event)
- `: keepalive` — sent every 15s if no event, prevents proxy timeouts (ignore it)
- `data: {...}` — actual events to parse

**Parse logic (pseudo-code):**
```ts
const lines = chunk.split("\n\n");
for (const line of lines) {
  if (line.startsWith("data: ")) {
    const event = JSON.parse(line.slice(6));
    handle(event);
  }
}
```

---

## 3. Event Types

### Phase events
```ts
{ phase: "UNDERSTAND" | "DISCOVER" | "ENRICH" | "SYNTHESIZE", status: "start" | "ok" | "error" }

// ok events carry extra info:
{ phase: "UNDERSTAND", status: "ok", name: "Stripe" }
{ phase: "DISCOVER",   status: "ok", count: 8 }
{ phase: "ENRICH",     status: "ok", count: 8 }
{ phase: "SYNTHESIZE", status: "ok", count: 8 }
```

### Progress events (during phases)
```ts
{ phase: "UNDERSTAND", status: "progress", kind: "source_consulted",    payload: { domain: "stripe.com" } }
{ phase: "UNDERSTAND", status: "progress", kind: "field_extracted",     payload: { field: "employees", value: "4000" } }
{ phase: "DISCOVER",   status: "progress", kind: "candidate_found",     payload: { name: "Braintree", website: "braintree.com" } }
{ phase: "ENRICH",     status: "progress", kind: "competitor_enriched", payload: { name: "Braintree" } }
{ phase: "ENRICH",     status: "progress", kind: "task_polled",         payload: { completed: 3, total: 8 } }
```

### Final result
```ts
{ result: RadarOutput, from_cache: boolean }
```

### Error
```ts
{ error: "string describing what went wrong" }
```

---

## 4. `RadarOutput` — Full JSON Shape

This is what you receive in `event.result`. All keys are **camelCase**.

```ts
interface RadarOutput {
  query: {
    url: string;          // "stripe.com"
    name: string;         // "Stripe"
    scannedAt: string;    // ISO 8601
    durationMs: number;   // pipeline duration
    sourcesScanned: number;
  };

  subject: RadarCompany;        // the analyzed company
  competitors: RadarCompany[];  // discovered competitors

  features: {
    group: string;   // feature category, e.g. "Payments"
    label: string;   // feature name, e.g. "Recurring billing"
  }[];

  capabilities: Record<string, ("full" | "part" | "none" | "soon")[]>;
  // key = company id (e.g. "stripe-com")
  // value = array aligned with `features` array
  // example: { "stripe-com": ["full", "full", "none"], "braintree-com": ["part", "none", "full"] }

  pricing: Record<string, PricingTier[]>;
  // key = company id
  // value = pricing tiers for that company

  funding: Record<string, FundingEvent[]>;
  // key = company id
  // value = funding rounds timeline

  radar: {
    axes: string[];                       // ["Breadth", "Depth", "Global", "Developer", "Pricing", "Trust"]
    scores: Record<string, number[]>;     // { "stripe-com": [80, 90, 75, 95, 60, 85] } — aligned with axes
    defs: Record<string, string>;         // axis definitions
  };
}
```

---

## 5. `RadarCompany` — Full Shape

Used for both `subject` and each item in `competitors`.

```ts
interface RadarCompany {
  id: string;               // slugified domain: "stripe-com"
  name: string;             // "Stripe"
  domain: string;           // "stripe.com"
  tagline: string;          // one-liner description
  category: string;         // primary market: "Payments"
  subCategory: string;      // secondary: "Online Payments"
  hq: string;               // "San Francisco, United States"
  hqCoords: [number, number]; // [lat, lng]: [37.77, -122.41]
  offices?: string[];

  founded?: number | null;          // 2010
  employees?: number | null;        // 4000
  employeeGrowth?: number;          // 0.12 = 12%

  funding?: {
    total: number;          // EUR
    lastRound: string;      // "Series H"
    lastRoundAt: string;    // "2021-03"
  } | null;

  investors?: string[];
  pricing?: {
    model: string;          // "usage-based"
    startsAt: number;       // 0 = free tier exists
    mention: string;        // "2.9% + 30¢ per transaction"
  } | null;

  arr?: number | null;
  customers?: number | null;
  avgContract?: number | null;
  notable?: string[];       // notable customers or signals

  isSubject?: boolean;      // true only for the analyzed company
  similarity?: number | null;  // 0.0–1.0 (placeholder: 0.5 for now)
  threat?: "high" | "medium" | "low" | null;  // (placeholder: "medium" for now)
}
```

---

## 6. Lookup Pattern for Capabilities / Pricing / Funding

All three dicts use **company `id`** as key.

```ts
const subjectId = output.subject.id;           // "stripe-com"
const subjectScores = output.radar.scores[subjectId]; // [80, 90, 75, ...]
const subjectCaps = output.capabilities[subjectId];   // ["full", "none", "part", ...]
const subjectFunding = output.funding[subjectId];     // [{ y: 2021, q: 1, amt: 600000000, round: "Series H" }]
```

`capabilities` and `features` are **aligned arrays** — `capabilities[id][i]` is the capability for `features[i]`.

---

## 7. camelCase Convention — Why & How

The backend is Python (uses `snake_case`). The JSON output is **auto-converted to camelCase** via Pydantic's `alias_generator=to_camel`.

You never need to do any conversion — what you receive from the API is already camelCase.

**Mapping examples:**
| Python field (backend) | JSON key (what you receive) |
|---|---|
| `sub_category` | `subCategory` |
| `hq_coords` | `hqCoords` |
| `is_subject` | `isSubject` |
| `employee_growth` | `employeeGrowth` |
| `scanned_at` | `scannedAt` |
| `duration_ms` | `durationMs` |
| `last_round_at` | `lastRoundAt` |

> **Rule:** if you add a new field to the Python model, the JSON key will be its camelCase version. No config needed.

---

## 8. Placeholder Values (current state)

Some fields are stubbed while the synthesize phase is being built:

| Field | Current value | Final behaviour |
|---|---|---|
| `similarity` | `0.5` for all competitors | ML-based score 0.0–1.0 |
| `threat` | `"medium"` for all competitors | Derived from funding + growth signals |
| `capabilities` | empty dict `{}` | Feature matrix from enrich phase |
| `features` | empty list `[]` | Feature list from enrich phase |

---

## 9. Cached Responses

When the same domain was scanned recently, the stream skips all phase events and sends only:

```ts
data: { result: RadarOutput, from_cache: true }
```

Handle `from_cache` to optionally show a "cached" indicator in the UI.

---

## 10. Error Handling

| Scenario | What you receive |
|---|---|
| Invalid URL | HTTP 422 before stream starts |
| Rate limit exceeded | HTTP 429 before stream starts |
| Pipeline error mid-stream | `data: { error: "message" }` |
| Client disconnects | Backend cancels pipeline (stops burning API credits) |

---

## Quick Reference: Existing Hook

The SSE parsing is already implemented in [`radar/frontend/src/hooks/useSseScan.ts`](../radar/frontend/src/hooks/useSseScan.ts).

```ts
import { useSseScan } from "@/hooks/useSseScan";

const { state, run, reset } = useSseScan(apiUrl);
// state.result: RadarOutput | null
// state.phases: { UNDERSTAND, DISCOVER, ENRICH } → "idle" | "running" | "done" | "error"
// state.events: progress events array
run("stripe.com");
```
