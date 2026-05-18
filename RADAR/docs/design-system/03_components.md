# 03 — Components

The component library. Each entry defines anatomy, states, props, and usage rules. Components are implemented in `radar/frontend/src/components/` and must consume tokens from `src/design-system/tokens.ts`.

This catalog is **non-exhaustive on purpose** — it covers the primitives needed for the landing + loading rebuild. Dashboard components will be added later.

---

## Primitives

### `StatusDot`

A small filled circle indicating state. Used everywhere — phase panels, top bar, log lines, command bar.

| State | Color | Animation |
|-------|-------|-----------|
| `active` | `status.active` (blue) | `pulse` (1500ms infinite) |
| `complete` | `status.complete` (white) | none |
| `pending` | `status.pending` (grey) | none |
| `error` | `status.error` (red) | none — used sparingly, true errors only |
| `live` | `status.active` (blue) | `pulse-slow` (2000ms) — used for "OPERATIONAL" indicator |

**Sizes:** `xs` (6px), `sm` (8px, default), `md` (10px).

**Anatomy:** circle, no border, no fill gradient. Optional concentric outer ring at 30% opacity (4px wider than dot) for `active` state.

---

### `StatusIndicator`

A small inline status text + dot, used in `TopBar` and `CommandBar` to show system or operation state.

**Anatomy:**
- Layout: `StatusDot` (sm) + text label, gap `space.2`
- Text: `fontFamily.mono`, `text.xs`, `weight.medium`, `tracking.wider`, uppercase
- Color: `fg.secondary` for the label
- No background, no border (it's chrome, not a chip)

**Variants by context:**
- System (top bar): blue dot + `OPERATIONAL` text, slow pulse
- Operation (command bar): blue dot + `ANALYZING` (active) / white dot + `COMPLETE` / red dot + `FAILED`

**Don't:** use in body content. This is chrome.

---

### `SearchInput`

The hero input. Single-line, dark, mono.

**Anatomy:**
- Container: full width up to `max-w-2xl`, `surface.inset`, 1px `line.subtle`, `radius.md`
- Left prefix: `▸` cursor cue, `fg.muted`, `fontFamily.mono`, `space.4` left padding
- Input: `fontFamily.mono`, `text.base`, `fg.primary` placeholder `fg.muted`, no border, transparent bg
- Right: `RUN ANALYSIS →` button (see `Button`), inset by `space.2`
- Focus: border becomes `line.strong`, shadow `shadow.focus`, transition `duration.fast ease.standard`

**Height:** `space.12` (48px) default, `space.16` (64px) on hero.

**Props:** `value`, `onChange`, `onSubmit`, `placeholder`, `disabled`, `size: 'default' | 'hero'`.

---

### `Button`

**Variants:**
- `primary` — `accent.500` text white. Hover `accent.600`, active `accent.700`.
- `secondary` — `surface.panel` text primary, border `line.subtle`. Hover `surface.raised`.
- `ghost` — transparent bg, text secondary. Hover `surface.raised`, text primary.
- `danger` — `status.error` text white. Used for destructive only.

**Sizes:** `sm` (32px height), `md` (40px, default), `lg` (48px, used on hero).

**Anatomy:**
- Font: `fontFamily.sans` (or `fontFamily.mono` if button label is uppercase/technical)
- Weight: `medium`
- Tracking: `wide` for uppercase labels
- Radius: `md`
- Padding: `space.3 space.4` default

**Don't:** pill buttons. Don't drop shadows. Don't gradient fills.

---

### `Chip` / `SourcePill`

Small inline tags. Two flavors:

**`Chip`** — generic
- Used for sample queries, badges, status indicators
- Anatomy: `fontFamily.mono` `text.xs`, padding `space.1 space.2`, radius `sm`, border `line.subtle`, bg `surface.panel`
- Hover: bg `surface.raised`, border `line.default`

**`SourcePill`** — citing a source
- Used in phase panels and dashboard to cite sources
- Anatomy: same as `Chip` + 14×14px favicon on the left (or 1×1 fallback square if missing)
- Text: domain only (`crunchbase.com`, not full URL)
- Clickable: opens the source in a new tab, `cursor-pointer`

---

### `Panel`

The fundamental container. Everything in the app lives inside a Panel.

**Anatomy:**
- Background: `surface.panel`
- Border: 1px `line.subtle`
- Radius: `md`
- Padding: `space.6` (default), or override per use

**Props:** `header?: ReactNode`, `footer?: ReactNode`, `state?: 'default' | 'active' | 'complete' | 'pending' | 'error'`.

**State styling:**
- `active` — left border 2px `status.active` (blue), subtle scanning border animation
- `complete` — left border 2px `status.complete` (white)
- `pending` — opacity 0.5
- `error` — left border 2px `status.error` (red, rare)

---

### `LogLine`

A single line in the live log.

**Anatomy:**
- Single line, no wrap (overflow ellipsis)
- Font: `fontFamily.mono`, `text.sm`
- Color: `fg.secondary` for default
- Pattern: `[HH:MM] [PHASE] message`
- Phase prefix color: **all 3 phases share `status.active` (blue) when their phase is active, `fg.muted` when complete/inactive**. Single-accent palette — no per-phase color coding.

**Animation:** newly appended lines type-on (30ms/char, max 30 chars animated then snap). Older lines remain static.

---

## Composed components

### `TopBar` (landing)

Thin horizontal bar across the top of the landing screen.

**Anatomy:**
- Height: `space.10` (40px)
- Background: `surface.base` (transparent over background)
- Bottom border: 1px `line.subtle`
- Padding: `space.4` horizontal

**Content:**
- Left: `RADAR` wordmark, `fontFamily.mono`, `weight.semibold`, `tracking.tight`, `fg.primary`
- Right slot: `StatusIndicator` (blue dot + `OPERATIONAL`) · version label `v0.3`
- **No classification chip.** Keep it minimal — version + system status only.

---

### `CommandBar` (loading + dashboard)

Replaces the hero on submission. Slightly taller than `TopBar`.

**Anatomy:**
- Height: `space.12` (48px)
- Background: `surface.panel`
- Bottom border: 1px `line.subtle`
- Padding: `space.4` horizontal

**Content:**
- Left: `RADAR` wordmark
- Center-left: `<domain>` (mono, e.g., `doctolib.fr`) — no `TARGET:` prefix, just the domain
- Center-right: `StatusIndicator` — blue dot + `ANALYZING` (active) / white dot + `COMPLETE`
- Right: timer `00:42` (mono, tabular nums)
- **No classification chip.**

---

### `PhasePanel`

A `Panel` specialized for the Operations Console.

**Anatomy:**
- Header row: `StatusDot` + phase name (mono uppercase) + status text (sm muted) + elapsed/expected time (mono right-aligned)
- Body: list of one-line bullets ("data points"), each prefixed with `•` or a tiny check
- Footer: row of `SourcePill`s

**States:** inherits from `Panel` (`active` / `complete` / `pending` / `error`).

**Props:**
```
{
  phase: 'UNDERSTAND' | 'DISCOVER' | 'ENRICH'
  state: 'active' | 'complete' | 'pending' | 'error'
  elapsedMs: number
  expectedMs: number      // 15000 / 20000 / 60000
  dataPoints: { label: string; value?: string }[]
  sources: { domain: string; faviconUrl?: string }[]
}
```

---

### `LiveLog`

A `Panel` containing a scrollable list of `LogLine`s.

**Anatomy:**
- Header row: `LIVE LOG` label (mono uppercase) + auto-scroll toggle (`▼ AUTO` chip)
- Body: vertical stack of `LogLine`s, newest at the bottom
- Max height: ~200px on desktop, collapsed by default on mobile
- Auto-scroll: snap to bottom when new lines arrive, unless user has scrolled up (then show "↓ N new" pill)

**Props:**
```
{
  lines: LogEntry[]
  maxLines?: number   // default 200, older lines pruned
}
```

---

### `SampleChips` (landing)

A horizontal row of clickable `Chip`s used to populate the search input.

**Anatomy:** small row of `Chip`s with `fontFamily.mono` `text.sm`. Clicking auto-fills the input and submits.

**Content (current default):** `doctolib.fr` `notion.so` `linear.app` `pennylane.com` `alan.com`

---

## Don't-build list

These are tempting but actively wrong for our audience. Do not build:

- **Tooltips that explain product features** — VCs already understand competitive intelligence. Tooltips signal "we think you're confused."
- **Onboarding overlays / tours** — same reason.
- **"Pro tip" callouts** — patronizing.
- **Animated illustrations / heroes with cartoons** — anti-credibility.
- **Toast notifications for routine success** — silence is the success state.
