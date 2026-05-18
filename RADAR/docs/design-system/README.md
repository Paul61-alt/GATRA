# RADAR Design System

> Intelligence Ops — Palantir corporate × Perplexity transparency.

A design system for RADAR, the competitive intelligence platform built by team GATRA. Targets VCs and corporate strategy teams who live in dense data tools and have zero tolerance for fluff.

## Why a design system

We are scaling beyond a single page. Every new surface (landing, loading console, dashboard, exports, future internal tools) needs to share the same visual language and interaction patterns. The system exists to:

1. **Speed up decisions.** Designers and engineers reach for tokens, not personal taste.
2. **Enforce credibility.** Consistency is what makes a tool feel "operational" rather than "marketing."
3. **Document intent.** Tokens encode our choices so future changes are deliberate, not accidental.

## Structure (hybrid: docs + code)

```
RADAR/
├── docs/design-system/              ← human-readable specs (this folder)
│   ├── 00_principles.md             ← what we believe
│   ├── 01_visual_language.md        ← mood, references, what we do/don't do
│   ├── 02_tokens.md                 ← color, type, spacing, motion (spec)
│   ├── 03_components.md             ← component specs (props, states, anatomy)
│   ├── 04_motion.md                 ← easings, durations, motion patterns
│   ├── 05_voice.md                  ← microcopy, intel jargon, tone
│   ├── 06_iconography.md            ← icon rules
│   └── moodboard/                   ← reference screenshots
│
└── radar/frontend/src/design-system/  ← machine-readable tokens (code)
    ├── tokens.ts                      ← TypeScript constants (source of truth)
    └── tailwind.preset.ts             ← Tailwind preset consuming tokens.ts
```

**Rule:** any new UI work — landing, loading console, dashboard, every future surface — must consume tokens from `src/design-system/tokens.ts` and Tailwind classes generated from the preset. No hard-coded colors, no inline spacing values, no one-off fonts.

## Where to start

- **New to the project?** Read `00_principles.md` then `01_visual_language.md`.
- **Designing a component?** Read `03_components.md` and `02_tokens.md`.
- **Writing copy?** Read `05_voice.md`.
- **Implementing in code?** Import from `src/design-system/tokens.ts` and use the Tailwind preset.

## Versioning

This system is v0 — pre-production. Breaking changes allowed until v1.0. After v1.0, semver applies.

## Maintainers

GATRA team. Decisions reviewed by Paul Pietra (paul.pietra@doctolib.com).
