/**
 * RADAR Design Tokens
 *
 * Single source of truth for color, typography, spacing, motion.
 * Consumed by tailwind.preset.ts and (rarely) by components for inline styles.
 *
 * Human-readable spec: /RADAR/docs/design-system/02_tokens.md
 * Rule: never hard-code color/spacing/font values elsewhere. Import from here.
 *
 * PALETTE — 3 colors only: black + white + electric blue.
 * State (active/complete/pending) is communicated via opacity/weight/motion,
 * not via separate hues. Red is kept as an escape hatch for true errors only.
 *
 * Tailwind class naming convention:
 *   color.surface.panel → bg-surface-panel
 *   color.line.subtle   → border-line-subtle
 *   color.fg.primary    → text-fg-primary
 *   color.accent[500]   → bg-accent-500, text-accent-500
 *   color.status.active → bg-status-active (aliased to accent-500)
 *   color.tint.accent   → bg-tint-accent (translucent blue bg)
 */

// ─────────────────────────────────────────────────────────────────────────────
// Color
// ─────────────────────────────────────────────────────────────────────────────

const surface = {
  base: "#0a0a0f", // app background
  panel: "#12121a", // elevated panels, cards
  inset: "#0d0d14", // inputs, code blocks
  raised: "#1a1a26", // hover state on interactive surfaces
} as const;

const line = {
  subtle: "#1f1f2e",
  default: "#2a2a3d",
  strong: "#3d3d57",
} as const;

const fg = {
  primary: "#ffffff",
  secondary: "#b4b4c7",
  muted: "#8b8b9e",
  disabled: "#5a5a6e",
  inverse: "#0a0a0f",
} as const;

const accent = {
  50: "#eff6ff",
  500: "#3b82f6", // electric blue — primary action, active state, highlights
  600: "#2563eb",
  700: "#1d4ed8",
  glow: "rgba(59,130,246,0.15)",
} as const;

/**
 * Semantic state aliases — these reference the 3-color palette.
 * Use these in component code for clarity (`bg-status-active` reads better
 * than `bg-accent-500` when meaning "this state is active").
 */
const status = {
  active: accent[500], // blue — in progress, currently working
  complete: fg.primary, // white — finished, verified
  pending: fg.disabled, // grey — not started, dimmed
  error: "#ef4444", // red — escape hatch, used sparingly
} as const;

/**
 * Translucent tints — used for chip backgrounds, subtle highlights.
 * Only two: accent (blue) and error (red).
 */
const tint = {
  accent: "rgba(59,130,246,0.1)",
  error: "rgba(239,68,68,0.1)",
} as const;

/** Data viz palette (charts, maps) — kept available but used minimally in v0. */
const data = {
  1: accent[500], // electric blue
  2: "#a855f7", // violet
  3: "#ec4899", // pink
  4: "#06b6d4", // cyan
  5: "#fb7185", // rose
  6: "#84cc16", // lime
} as const;

export const color = {
  surface,
  line,
  fg,
  accent,
  status,
  tint,
  data,
} as const;

// ─────────────────────────────────────────────────────────────────────────────
// Typography
// ─────────────────────────────────────────────────────────────────────────────

export const fontFamily = {
  mono: [
    "JetBrains Mono",
    "ui-monospace",
    "SFMono-Regular",
    "Menlo",
    "monospace",
  ],
  sans: [
    "Inter",
    "ui-sans-serif",
    "system-ui",
    "-apple-system",
    "sans-serif",
  ],
} as const;

export const fontSize = {
  xs: "0.6875rem", // 11px
  sm: "0.8125rem", // 13px
  base: "0.9375rem", // 15px
  md: "1.0625rem", // 17px
  lg: "1.375rem", // 22px
  xl: "1.875rem", // 30px
  "2xl": "2.5rem", // 40px
  "3xl": "3.5rem", // 56px
} as const;

export const fontWeight = {
  normal: "400",
  medium: "500",
  semibold: "600",
  bold: "700",
} as const;

export const lineHeight = {
  tight: "1.1",
  snug: "1.25",
  normal: "1.5",
  relaxed: "1.65",
} as const;

export const letterSpacing = {
  tight: "-0.02em",
  normal: "0",
  wide: "0.05em",
  wider: "0.12em",
} as const;

// ─────────────────────────────────────────────────────────────────────────────
// Spacing (4px grid)
// ─────────────────────────────────────────────────────────────────────────────

export const spacing = {
  0: "0",
  1: "0.25rem", // 4
  2: "0.5rem", // 8
  3: "0.75rem", // 12
  4: "1rem", // 16
  5: "1.25rem", // 20
  6: "1.5rem", // 24
  8: "2rem", // 32
  10: "2.5rem", // 40
  12: "3rem", // 48
  16: "4rem", // 64
  20: "5rem", // 80
  24: "6rem", // 96
} as const;

// ─────────────────────────────────────────────────────────────────────────────
// Radius
// ─────────────────────────────────────────────────────────────────────────────

export const radius = {
  none: "0",
  sm: "2px",
  md: "4px",
  lg: "6px",
  full: "9999px", // restricted use — dot indicators only
} as const;

// ─────────────────────────────────────────────────────────────────────────────
// Shadow
// ─────────────────────────────────────────────────────────────────────────────

export const shadow = {
  focus: `0 0 0 3px ${accent.glow}`,
  panel: `0 1px 0 0 ${line.subtle} inset`,
} as const;

// ─────────────────────────────────────────────────────────────────────────────
// Motion
// ─────────────────────────────────────────────────────────────────────────────

export const duration = {
  instant: "80ms",
  fast: "160ms",
  normal: "240ms",
  slow: "400ms",
  hero: "600ms",
} as const;

export const ease = {
  standard: "cubic-bezier(0.2, 0.8, 0.2, 1)",
  in: "cubic-bezier(0.4, 0, 1, 1)",
  out: "cubic-bezier(0, 0, 0.2, 1)",
  linear: "linear",
} as const;

// ─────────────────────────────────────────────────────────────────────────────
// Layout
// ─────────────────────────────────────────────────────────────────────────────

export const breakpoint = {
  sm: "640px",
  md: "768px",
  lg: "1024px",
  xl: "1280px",
  "2xl": "1536px",
} as const;

export const zIndex = {
  base: 0,
  elevated: 10,
  dropdown: 100,
  modal: 1000,
  toast: 10000,
} as const;

// ─────────────────────────────────────────────────────────────────────────────
// Animation keyframes (consumed by tailwind preset)
// ─────────────────────────────────────────────────────────────────────────────

export const keyframes = {
  pulse: {
    "0%, 100%": { opacity: "0.4" },
    "50%": { opacity: "1" },
  },
  "pulse-slow": {
    "0%, 100%": { opacity: "0.5" },
    "50%": { opacity: "1" },
  },
  scan: {
    "0%": { transform: "translateY(-100%)" },
    "100%": { transform: "translateY(200vh)" },
  },
  enter: {
    "0%": { opacity: "0", transform: "translateY(4px)" },
    "100%": { opacity: "1", transform: "translateY(0)" },
  },
  exit: {
    "0%": { opacity: "1", transform: "translateY(0)" },
    "100%": { opacity: "0", transform: "translateY(-4px)" },
  },
} as const;

export const animation = {
  pulse: `pulse 1500ms ${ease.in} infinite`,
  "pulse-slow": `pulse-slow 2000ms ${ease.in} infinite`,
  scan: `scan 8000ms ${ease.linear} infinite`,
  enter: `enter ${duration.fast} ${ease.out} both`,
  exit: `exit ${duration.instant} ${ease.in} both`,
} as const;

// ─────────────────────────────────────────────────────────────────────────────
// Type exports
// ─────────────────────────────────────────────────────────────────────────────

export type ColorTokens = typeof color;
export type SpacingToken = keyof typeof spacing;
export type FontSizeToken = keyof typeof fontSize;
export type RadiusToken = keyof typeof radius;
export type DurationToken = keyof typeof duration;
export type EaseToken = keyof typeof ease;
