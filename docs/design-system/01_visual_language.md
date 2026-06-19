# 01 — Visual Language

What RADAR looks and feels like, with references and explicit do/don't lists.

---

## Mood

Two anchors:

- **Palantir Foundry / Gotham** — dark, dense, classified-document feel. Surfaces are flat. Information is hierarchical. Status is always visible. The product looks like it belongs in a war room.
- **Perplexity (Research mode)** — modern AI transparency. Streaming text. Source cards. Step-by-step reasoning visible. The product respects the user enough to show its work.

The combination: **corporate intelligence aesthetics + modern AI transparency UX.**

Adjacent references (use sparingly):

- **Bloomberg Terminal** — ticker rhythm, monospace data, dense layouts. Take the rhythm and the rigor; **do not** take the multi-color status palette — RADAR is restricted to black + white + electric blue.
- **Linear** — keyboard-driven density, restraint, sharp typography. Take the restraint, not the brand color.
- **Vercel dashboards** — dark + clean + technical. Take the panel composition.

Anti-references (what we are NOT):

- Consumer SaaS landing pages (Notion, Linear marketing site, Stripe marketing).
- Anything Vue/Material/Bootstrap default.
- Glass / frosted / neumorphic styles.
- Anything that looks like an Apple product.

---

## Do / Don't

### Surfaces

| Do | Don't |
|----|-------|
| Solid dark surfaces with 1px borders | Gradients on surfaces |
| 2–4px corner radius (square-ish) | Pill / fully rounded shapes |
| Elevation via lighter surface + border | Drop shadows for decoration |
| Subtle 1px grid background (5% opacity) | Patterned or textured backgrounds |

### Typography

| Do | Don't |
|----|-------|
| JetBrains Mono for data, IDs, paths | Mono everywhere (illegible for prose) |
| Inter (or grotesk) for prose, headings | Serifs anywhere |
| Tabular numerals always | Proportional numerals in data |
| Generous tracking on uppercase labels | Tight default tracking on caps |

### Color

| Do | Don't |
|----|-------|
| Single accent (electric blue) for primary action and active state | Multi-color status palette |
| State via opacity/weight/motion + single blue accent | Green/amber/red zoo for state |
| Red ONLY for true errors (escape hatch) | Red as decoration |
| 60-30-10: dark surface / borders+muted text / blue accent | Bright fills covering large areas |
| White text at full opacity for primary, 60% for secondary | Multiple greys for text hierarchy |

### Motion

| Do | Don't |
|----|-------|
| Functional motion (state change, causality) | Decorative motion (sparkles, bouncing) |
| 120–240ms standard, 400ms morph, 600ms hero | Anything > 800ms |
| Status pulses, scan lines, type-on text | Confetti, particles, ease-bounce |
| `cubic-bezier(0.2, 0.8, 0.2, 1)` | `ease-in-out` for everything |

### Iconography

| Do | Don't |
|----|-------|
| Lucide icons, 1.5px stroke, 16/20px sizes | Filled icons, multicolor icons |
| Icons only when they add scan speed | Icons next to every label |
| Geometric, technical glyphs | Friendly / round / hand-drawn glyphs |

### Imagery

| Do | Don't |
|----|-------|
| Favicons in source pills | Stock illustrations |
| Maps, charts, data viz | Photos of teams or offices |
| ASCII art in code samples | Emoji in product UI |

---

## The 10-second test

When a VC opens RADAR for the first time, in 10 seconds they should think:

> "This is a serious tool. Not a marketing page. It probably knows what it's doing."

NOT:

> "Cute landing page. Wonder what the product actually does."

If we ever fail the 10-second test in user testing, we re-read this doc.

---

## Moodboard

See `/moodboard/` for reference screenshots. Always check the moodboard before pushing a visual change.
