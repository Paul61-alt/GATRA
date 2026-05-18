# 05 — Voice & Tone

How RADAR talks to the user. Microcopy guidelines, the intel-jargon glossary, and rules for the live log.

---

## Voice attributes

RADAR's voice is:

1. **Terse** — fewer words win. If a label can be cut, cut it.
2. **Technical** — assume the reader is an analyst. Don't simplify what doesn't need simplifying.
3. **Confident** — state facts. Avoid "perhaps," "we think," "maybe."
4. **Source-aware** — when in doubt, cite. "Founded 2013 · crunchbase.com" beats "Founded around 2013."
5. **Operational, not promotional** — describe what the system does, not how amazing it is.

What RADAR is **not**:

- Friendly. (Friendly products waste analyst time.)
- Apologetic. (We don't say "sorry, please try again." We say "Retry.")
- Marketing. (No "powerful," "seamless," "revolutionary.")
- Cute. (No puns, no exclamation marks, no emoji.)

---

## Microcopy patterns

### Buttons / actions

| Don't | Do |
|-------|-----|
| Get Started | Run Analysis |
| Click here to analyze | Run Analysis → |
| Submit | Run Analysis |
| Please wait... | Analyzing |
| Oops! Something went wrong | Analysis failed |
| Try again? | Retry |
| Cancel | Cancel (or Abort for in-progress) |

### Status text

| Phase state | Label |
|-------------|-------|
| Not started | `PENDING` |
| Active | `IN PROGRESS` |
| Done | `COMPLETE` |
| Failed | `FAILED` |
| Aborted | `ABORTED` |

System state (top bar):

| Underlying | Label |
|------------|-------|
| All systems up | `SYSTEM OPERATIONAL` |
| Degraded (backend slow) | `SYSTEM DEGRADED` |
| Down | `SYSTEM OFFLINE` |
| Maintenance | `MAINTENANCE` |

### Empty / null states

| Situation | Copy |
|-----------|------|
| No data extracted for a field | `Unavailable` (mono, muted) |
| No source cited | `Source: internal` or omit |
| 0 results | `No results.` (period included) |
| Pre-analysis | `Awaiting input.` |

### Errors

Pattern: `[what failed]. [what to do].`

Examples:
- `Invalid domain. Enter a valid URL.`
- `Analysis timed out. Retry or try a different domain.`
- `Unable to reach Linkup API. Check connection and retry.`

Never: "Oops!", "Whoops!", "Something went wrong" without specifics.

---

## Functional vocabulary

A small set of terms used deliberately for consistency. Functional only — no decorative "intel agency" jargon. The product wins credibility through how it works (live sourcing, real data, transparency), not through cosplay.

| Term | Meaning | Used where |
|------|---------|------------|
| **OPERATIONAL** | System is up and ready | Top bar status indicator |
| **ANALYZING** | A run is in progress | Command bar, phase headers |
| **COMPLETE** | A run or phase finished | Command bar, phase headers |
| **PENDING** | A phase not yet started | Phase headers |
| **FAILED** | A phase or run errored | Command bar, phase headers (rare) |
| **SOURCE** | A URL/citation backing a fact | Source pills |
| **CONFIDENCE** | The confidence score (0.0–1.0) | DataPoint metadata |
| **SIGNAL** | A recent pricing/funding/news event | Pricing feed |

**Explicitly dropped** (do not reintroduce): `TIER 1 INTEL`, `CLASSIFIED`, `INTERNAL`, `OPERATION`, `DOSSIER` (as decorative chrome). These feel gimmicky and dilute the credibility we're after. Use plain functional language.

**Domain naming:** when referring to the company being analyzed, just show the domain (`doctolib.fr`), no `TARGET:` prefix.

---

## Live log writing rules

Each log line answers one of three questions:

1. **What did we just check?** → `[UNDERSTAND] Consulted: crunchbase.com/doctolib`
2. **What did we just find?** → `[UNDERSTAND] Extracted: founding_year (2013)`
3. **What's the progress?** → `[ENRICH] Polled tasks: 12/30 complete`

### Format

```
HH:MM [PHASE] verb: object
```

- Time is left-zero-padded mono.
- Phase is uppercase, color-coded.
- Verb is present-tense, ends with `:` if followed by a value.
- Object: the thing acted on. Mono if it's a URL/identifier, sans if it's prose.

### Verb glossary

Use these verbs only:

| Verb | Use |
|------|-----|
| `Consulted` | Hit a source URL |
| `Extracted` | Pulled a field from a source |
| `Geocoded` | Resolved a place to lat/lng |
| `Identified` | Found a candidate (competitor) |
| `Filtered` | Deduped or excluded |
| `Polled` | Checked a batch task status |
| `Enriched` | Built a competitor profile |
| `Failed` | Phase or sub-step error |
| `Complete` | Phase finished |

Don't use: "Loading," "Working on," "Processing," "Doing." These are passive and uninformative.

### Length

- Hard cap: 80 characters per line. If longer, ellipsis-truncate the object.
- Soft target: 40–60 characters. Logs scan faster when uniform.

### Example sequence (a full UNDERSTAND phase)

```
00:01 [UNDERSTAND] Consulted: doctolib.fr/about
00:02 [UNDERSTAND] Consulted: crunchbase.com/organization/doctolib
00:04 [UNDERSTAND] Extracted: founding_year (2013)
00:04 [UNDERSTAND] Extracted: hq.country (FR)
00:06 [UNDERSTAND] Geocoded: Paris, FR (48.85, 2.35)
00:08 [UNDERSTAND] Extracted: funding.rounds (3 found)
00:11 [UNDERSTAND] Extracted: employees (2,500+)
00:14 [UNDERSTAND] Complete (15.2s)
```

---

## Language

Default to **English** for all product UI and logs. Internal docs (CLAUDE.md, planning) can be in French — that's an internal tool choice. The product itself, including microcopy, is English-only at v0.
