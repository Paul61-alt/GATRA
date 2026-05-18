# 02 — Tokens

The complete spec of every design token. The TypeScript source of truth lives at `radar/frontend/src/design-system/tokens.ts` — this document is the human-readable mirror.

When a value disagrees between this doc and `tokens.ts`, **the code wins** and this doc must be updated.

---

## Naming convention

Tokens are organized by **semantic role**, not by Tailwind utility. The mapping to Tailwind class names is direct:

| Token group | Tailwind class prefix | Example |
|-------------|----------------------|---------|
| `color.surface.*` | `bg-surface-*` | `bg-surface-panel` |
| `color.line.*` | `border-line-*` | `border-line-subtle` |
| `color.fg.*` | `text-fg-*` | `text-fg-primary` |
| `color.accent.*` | `bg-accent-*` / `text-accent-*` | `bg-accent-500` |
| `color.status.*` | `bg-status-*` / `text-status-*` | `text-status-ok` |
| `color.tint.*` | `bg-tint-*` | `bg-tint-ok` (translucent chip bg) |
| `color.data.*` | `bg-data-*` / `text-data-*` | `text-data-1` |

`tint.*` is the translucent counterpart of `status.*` — use it for chip backgrounds, subtle highlights. Use `status.*` for dots, text, solid swatches.

---

## Color

### Surface (backgrounds)

| Token | Value | Use |
|-------|-------|-----|
| `surface.base` | `#0a0a0f` | App background (also `bg-surface-base`, but body is already set) |
| `surface.panel` | `#12121a` | Panels, cards, dropdowns |
| `surface.inset` | `#0d0d14` | Form inputs, code blocks |
| `surface.raised` | `#1a1a26` | Hover state on interactive surfaces |

### Line (borders)

| Token | Value | Use |
|-------|-------|-----|
| `line.subtle` | `#1f1f2e` | Default panel/input border |
| `line.default` | `#2a2a3d` | Hovered or emphasized border |
| `line.strong` | `#3d3d57` | Focus ring, selected state |

### Fg (text)

| Token | Value | Use |
|-------|-------|-----|
| `fg.primary` | `#ffffff` | Headlines, primary content |
| `fg.secondary` | `#b4b4c7` | Body prose, labels |
| `fg.muted` | `#8b8b9e` | Metadata, captions, placeholders |
| `fg.disabled` | `#5a5a6e` | Disabled state |
| `fg.inverse` | `#0a0a0f` | Text on light/accent surfaces (rare) |

### Accent (electric blue — primary action, active state)

| Token | Value | Use |
|-------|-------|-----|
| `accent.50` | `#eff6ff` | Rare — text on dark blue surface |
| `accent.500` | `#3b82f6` | Primary buttons, active borders, links |
| `accent.600` | `#2563eb` | Hover state on primary button |
| `accent.700` | `#1d4ed8` | Pressed state |
| `accent.glow` | `rgba(59,130,246,0.15)` | Focus ring, subtle highlight |

### Status (semantic state aliases)

The palette is **3 colors only: black + white + electric blue**. State is communicated through **opacity, weight, motion, and the single blue accent** rather than via separate hues. The `status.*` tokens are semantic aliases that map onto the 3-color palette — they exist so component code reads as `bg-status-active` rather than `bg-accent-500` when that's the intent.

| Token | Maps to | Use |
|-------|---------|-----|
| `status.active` | `accent.500` (blue) | In progress / currently working / pulsing |
| `status.complete` | `fg.primary` (white) | Finished / verified / done |
| `status.pending` | `fg.disabled` (grey) | Not started / dimmed |
| `status.error` | `#ef4444` (red) | True errors only — escape hatch, used sparingly |

### Tint (translucent backgrounds)

Only two translucent tints. Used for chip backgrounds, subtle highlights, focus halos.

| Token | Value | Use |
|-------|-------|-----|
| `tint.accent` | `rgba(59,130,246,0.1)` | Blue tinted background (highlight, active chip) |
| `tint.error` | `rgba(239,68,68,0.1)` | Red tinted background (error chip) |

### Data (viz palette)

Kept available for charts and maps but **used minimally in v0**. The default visualization in RADAR (competitor map markers, etc.) should use the 3-color palette + opacity variants first. Reach for the data palette only when a chart genuinely needs distinguishable categorical colors.

| Token | Value |
|-------|-------|
| `data.1` | `#3b82f6` (electric blue — same as accent) |
| `data.2` | `#a855f7` (violet) |
| `data.3` | `#ec4899` (pink) |
| `data.4` | `#06b6d4` (cyan) |
| `data.5` | `#fb7185` (rose) |
| `data.6` | `#84cc16` (lime) |

---

## Typography

### Families

| Token | Stack |
|-------|-------|
| `fontFamily.mono` | `JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, monospace` |
| `fontFamily.sans` | `Inter, ui-sans-serif, system-ui, -apple-system, sans-serif` |

Tailwind class: `font-mono`, `font-sans`.

### Scale

| Token | Value | Px | Tailwind | Use |
|-------|-------|----|----|-----|
| `fontSize.xs` | `0.6875rem` | 11 | `text-xs` | Status chips, micro-labels |
| `fontSize.sm` | `0.8125rem` | 13 | `text-sm` | Captions, metadata, source pills |
| `fontSize.base` | `0.9375rem` | 15 | `text-base` | Body, default UI |
| `fontSize.md` | `1.0625rem` | 17 | `text-md` | Subheads, emphasized body |
| `fontSize.lg` | `1.375rem` | 22 | `text-lg` | Card titles |
| `fontSize.xl` | `1.875rem` | 30 | `text-xl` | Section heads |
| `fontSize.2xl` | `2.5rem` | 40 | `text-2xl` | Hero secondary lines |
| `fontSize.3xl` | `3.5rem` | 56 | `text-3xl` | Hero headline (desktop) |

### Weight

| Token | Value | Tailwind | Use |
|-------|-------|----|-----|
| `fontWeight.normal` | `400` | `font-normal` | Body, prose |
| `fontWeight.medium` | `500` | `font-medium` | UI labels, button text |
| `fontWeight.semibold` | `600` | `font-semibold` | Subheads, emphasis |
| `fontWeight.bold` | `700` | `font-bold` | Headlines, key data points |

### Line height

| Token | Value | Tailwind | Use |
|-------|-------|----|-----|
| `lineHeight.tight` | `1.1` | `leading-tight` | Headlines |
| `lineHeight.snug` | `1.25` | `leading-snug` | Subheads |
| `lineHeight.normal` | `1.5` | `leading-normal` | Body prose |
| `lineHeight.relaxed` | `1.65` | `leading-relaxed` | Long-form reading |

### Letter spacing

| Token | Value | Tailwind | Use |
|-------|-------|----|-----|
| `letterSpacing.tight` | `-0.02em` | `tracking-tight` | Large headlines |
| `letterSpacing.normal` | `0` | `tracking-normal` | Default |
| `letterSpacing.wide` | `0.05em` | `tracking-wide` | Uppercase labels |
| `letterSpacing.wider` | `0.12em` | `tracking-wider` | Tiny uppercase eyebrows / status chips |

### Font features (set globally on body)

- `font-variant-numeric: tabular-nums`
- `font-feature-settings: "cv02", "cv03", "cv04", "cv11"` (Inter character variants — flat-top a, single-storey g, etc., subtle but cleaner for data UI)

---

## Spacing (4px base grid)

| Token | Value | Px | Tailwind |
|-------|-------|----|----|
| `spacing.0` | `0` | 0 | `p-0`, `m-0`, `gap-0` |
| `spacing.1` | `0.25rem` | 4 | `p-1` |
| `spacing.2` | `0.5rem` | 8 | `p-2` |
| `spacing.3` | `0.75rem` | 12 | `p-3` |
| `spacing.4` | `1rem` | 16 | `p-4` |
| `spacing.5` | `1.25rem` | 20 | `p-5` |
| `spacing.6` | `1.5rem` | 24 | `p-6` |
| `spacing.8` | `2rem` | 32 | `p-8` |
| `spacing.10` | `2.5rem` | 40 | `p-10` |
| `spacing.12` | `3rem` | 48 | `p-12` |
| `spacing.16` | `4rem` | 64 | `p-16` |
| `spacing.20` | `5rem` | 80 | `p-20` |
| `spacing.24` | `6rem` | 96 | `p-24` |

**Rules:**
- Default panel padding: `spacing.6` (24px) on desktop, `spacing.4` (16px) on mobile.
- Default data row gap: `spacing.2` to `spacing.3` (8–12px).
- Default section break: `spacing.12` to `spacing.16` (48–64px).
- Never use values outside this scale. If you need 13px, you're probably wrong about the design.

---

## Radius

| Token | Value | Tailwind | Use |
|-------|-------|----|-----|
| `radius.none` | `0` | `rounded-none` | Status indicators, log lines, dividers |
| `radius.sm` | `2px` | `rounded-sm` | Chips, badges, source pills |
| `radius.md` | `4px` | `rounded-md` | Default — buttons, inputs, cards, panels |
| `radius.lg` | `6px` | `rounded-lg` | Modals, large surfaces (rare) |
| `radius.full` | `9999px` | `rounded-full` | **Forbidden** outside dot indicators |

---

## Shadow

We don't use shadows for decoration. Elevation comes from background contrast + border.

Only two shadows exist:

| Token | Value | Tailwind | Use |
|-------|-------|----|-----|
| `shadow.focus` | `0 0 0 3px var(--accent-glow)` | `shadow-focus` | Input focus ring |
| `shadow.panel` | `0 1px 0 0 var(--line-subtle) inset` | `shadow-panel` | Optional 1px inner highlight on panels |

---

## Motion

### Durations

| Token | Value | Tailwind | Use |
|-------|-------|----|-----|
| `duration.instant` | `80ms` | `duration-instant` | Hover state, micro-feedback |
| `duration.fast` | `160ms` | `duration-fast` | Default — buttons, chips, panels appearing |
| `duration.normal` | `240ms` | `duration-normal` | Tooltips, dropdowns, panel content |
| `duration.slow` | `400ms` | `duration-slow` | Morph transitions, layout shifts |
| `duration.hero` | `600ms` | `duration-hero` | First-paint animations, big morphs |

### Easings

| Token | Value | Tailwind | Use |
|-------|-------|----|-----|
| `ease.standard` | `cubic-bezier(0.2, 0.8, 0.2, 1)` | `ease-standard` | Default — quick start, soft land |
| `ease.in` | `cubic-bezier(0.4, 0, 1, 1)` | `ease-in` | Things leaving the screen |
| `ease.out` | `cubic-bezier(0, 0, 0.2, 1)` | `ease-out` | Things arriving on screen |
| `ease.linear` | `linear` | `ease-linear` | Scan lines, continuous motion |

### Named animations (registered as Tailwind utilities)

| Class | Spec |
|-------|------|
| `animate-pulse` | 1500ms infinite, opacity 0.4 ↔ 1.0, used on `status.active` (blue) dots |
| `animate-pulse-slow` | 2000ms infinite, used on top-bar "live" dots |
| `animate-scan` | 8000ms infinite linear, 1px gradient line top-to-bottom of viewport |
| `animate-enter` | Element appearance (160ms, opacity + translateY) |
| `animate-exit` | Element disappearance (80ms, opacity + translateY) |

---

## Breakpoints

| Token | Value | Tailwind | Use |
|-------|-------|----|-----|
| `breakpoint.sm` | `640px` | `sm:*` | Phone landscape — small tweaks |
| `breakpoint.md` | `768px` | `md:*` | Tablet — panels stack |
| `breakpoint.lg` | `1024px` | `lg:*` | Laptop — full Operations Console |
| `breakpoint.xl` | `1280px` | `xl:*` | Desktop — wider panels |
| `breakpoint.2xl` | `1536px` | `2xl:*` | Large desktop — extra breathing room |

Desktop-first. Mobile is responsive but never primary.

---

## Z-index

Strict scale, no `z-index: 9999`.

| Token | Value | Tailwind | Use |
|-------|-------|----|-----|
| `zIndex.base` | `0` | `z-base` | Default content |
| `zIndex.elevated` | `10` | `z-elevated` | Sticky elements |
| `zIndex.dropdown` | `100` | `z-dropdown` | Dropdowns, popovers |
| `zIndex.modal` | `1000` | `z-modal` | Modals, dialogs |
| `zIndex.toast` | `10000` | `z-toast` | Toasts, error banners |
