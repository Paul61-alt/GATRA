# 04 — Motion

Motion conveys process. Decorative motion is forbidden (see principle #4).

This doc defines the named motion patterns used across RADAR. All durations and easings reference tokens defined in `02_tokens.md`.

---

## Pattern library

### `pulse` — "live"

Used on `StatusDot` when state is `active` (something is happening right now).

- Duration: 1500ms infinite
- Property: `opacity`
- Keyframes: `0% { opacity: 0.4 } 50% { opacity: 1 } 100% { opacity: 0.4 }`
- Easing: `ease-in-out`

A slower variant (2000ms) is used on the top bar `live` dot ("system operational").

---

### `scan` — ambient texture

A 1px gradient line that travels top-to-bottom across the viewport. Used **only on the landing hero**, never inside data surfaces. Adds a subtle "console" mood without being distracting.

- Duration: 8000ms infinite linear
- Property: `transform: translateY(-100% → 200%)`
- Opacity: 0.04 (extremely subtle)
- Gradient: `linear-gradient(180deg, transparent, accent.500, transparent)`
- Height: 1px, full viewport width

If a user prefers reduced motion (`prefers-reduced-motion: reduce`), disable.

---

### `type-on` — incoming data

Newly arriving log lines and data points appear character-by-character. Conveys "data is being received in real time."

- Speed: 30ms per character
- Cap: max 30 characters animated; beyond that, snap the rest in
- Cursor: optional 1px caret blinking during typing
- After typing: line becomes static (no perpetual cursor)

**Performance rule:** never run more than 3 type-on animations simultaneously. If more lines arrive at once, the newest types on, others snap in.

---

### `morph` — layout transformation

Used when a panel changes size, position, or role. Hero → command bar uses this. Operations Console → dashboard uses this.

- Duration: 400ms (token: `duration.slow`)
- Easing: `cubic-bezier(0.2, 0.8, 0.2, 1)` (token: `ease.standard`)
- Properties animated: `transform`, `width`, `height`, `opacity`
- Strategy: use FLIP technique (First, Last, Invert, Play) or CSS `view-transition-name` for cross-component morphs

**Don't:** fade out + fade in. That signals "replaced." Morph signals "transformed."

---

### `enter` — element first appearance

Default entrance for any newly inserted element (panel, chip, log line).

- Duration: 160ms (token: `duration.fast`)
- Easing: `cubic-bezier(0, 0, 0.2, 1)` (token: `ease.out`)
- Properties: `opacity 0 → 1`, optional `translateY(4px) → 0`

---

### `exit` — element disappearance

- Duration: 120ms
- Easing: `cubic-bezier(0.4, 0, 1, 1)` (token: `ease.in`)
- Properties: `opacity 1 → 0`, optional `translateY(0 → -4px)`

---

### `focus-ring` — input focus

Used when an interactive element receives focus.

- Duration: 80ms (token: `duration.instant`)
- Properties: border color (`subtle` → `strong`), box-shadow (`none` → `shadow.focus`)

---

### `count-up` — numeric reveal

When a final count appears (e.g., "8 competitors identified"), animate from 0 to N.

- Duration: 600ms
- Easing: `ease.out`
- Tick rate: 16ms (60fps)
- Format: respects locale formatting (`Intl.NumberFormat`)

---

## Reduced motion

We always respect `prefers-reduced-motion: reduce`. Mapping:

| Pattern | Reduced motion behavior |
|---------|-------------------------|
| `pulse` | Disabled (static at 1.0 opacity) |
| `scan` | Disabled (line hidden) |
| `type-on` | Disabled (lines snap in fully) |
| `morph` | Reduced to 80ms cross-fade |
| `enter` / `exit` | 80ms opacity only, no translate |
| `count-up` | Disabled (final number rendered directly) |

Implementation: a single `useReducedMotion` hook reads the media query and exposes a `prefersReduced` boolean. All motion components consult it.

---

## Performance budget

- No motion may cause a layout shift on the critical path (CLS = 0).
- All motion runs on `transform` and `opacity` only. Never animate `width`, `height`, `top`, `left` directly (unless inside a controlled morph via FLIP).
- Type-on capped at 3 concurrent. Pulses capped at 5 visible at once.
- If you find yourself adding `will-change` everywhere, you're working around the wrong thing.

---

## Decision rule

Before adding any animation, answer in one sentence: **"What state change does this motion communicate?"**

If the answer is "none, it just looks cool" — delete it.
