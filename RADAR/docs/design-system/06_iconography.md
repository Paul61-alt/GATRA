# 06 — Iconography

Rules for icon usage in RADAR.

---

## Icon set

**Lucide** (https://lucide.dev). Open source, MIT licensed, ~1500 icons, consistent geometric style.

Install: `npm install lucide-react`

Why Lucide:
- Geometric, technical, single-color glyphs
- Consistent 1.5px stroke weight (we set 1.75px in code for crisper rendering on dark)
- React component per icon (good tree-shaking)
- Active maintenance

**Don't mix icon sets.** No Heroicons + Lucide + Phosphor. Single source.

---

## Sizes

| Size | Px | Use |
|------|-----|-----|
| `xs` | 12 | Inline with `text.xs` (chip prefixes) |
| `sm` | 14 | Inline with `text.sm` (source pills, log lines) |
| `md` | 16 | Default — buttons, labels |
| `lg` | 20 | Headers, primary actions |
| `xl` | 24 | Hero / large-button icons |

Never use 13px, 15px, 17px, 18px. Stick to the scale.

---

## Stroke weight

Set globally on every icon:

```tsx
<Icon strokeWidth={1.75} />
```

Why 1.75: 1.5 (Lucide default) is too thin on dark backgrounds at small sizes; 2 is too heavy and trends consumer. 1.75 is the sweet spot.

For `xs` (12px), drop to `1.5`. For `xl` (24px+), keep `1.75`.

---

## Color

Icons are monochromatic and inherit `currentColor`.

- Default: `text.secondary` (`#b4b4c7`)
- Inside `StatusDot` contexts: match the status color
- In buttons: match the button's text color
- Disabled: `text.disabled`

**Never** use multi-color icons. Never use filled icons. Never use icons as decorative spot-art.

---

## When to use an icon

Icons exist to **increase scan speed**, not to decorate. Use one when:

✅ The action is universally recognized (search, close, copy, expand, external link)
✅ The icon replaces a redundant word ("→" instead of " Run Analysis Now ")
✅ The icon is a status indicator (check, warning triangle, error octagon)

**Don't** use one when:

❌ The label is already clear without it ("Cancel" doesn't need an X icon)
❌ The icon is novel/unrecognizable (people will guess what it means)
❌ You're trying to liven up a UI ("dashboard feels empty, let me add icons")

When in doubt, omit. A label-only UI is denser and faster to scan than a label-plus-icon UI.

---

## Custom glyphs (sparingly)

A few non-Lucide glyphs used in chrome only:

| Glyph | Use | Rendered |
|-------|-----|----------|
| `▸` | Search input prefix (cursor cue) | Unicode character |
| `→` | Action button affix | Unicode character |
| `•` | Bullet in data point lists | Unicode character |
| `◉` | Active status dot (deprecated — use `StatusDot` component) | Unicode character |
| `○` | Pending status dot (deprecated — use `StatusDot` component) | Unicode character |
| `✓` | Complete status check (deprecated — use Lucide `Check`) | Lucide |
| `⚡` | Cache hit badge | Unicode character |

Unicode glyphs are allowed for chrome (search prefix, button arrow, bullets). For interactive icons (toggles, status, actions), use Lucide.

---

## Implementation pattern

A tiny wrapper enforces the defaults:

```tsx
// src/components/Icon.tsx (to be created)
import * as Lucide from 'lucide-react'

type IconName = keyof typeof Lucide
type IconSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl'

const sizeMap: Record<IconSize, number> = { xs: 12, sm: 14, md: 16, lg: 20, xl: 24 }

export function Icon({
  name,
  size = 'md',
  className,
}: {
  name: IconName
  size?: IconSize
  className?: string
}) {
  const Component = Lucide[name] as React.FC<React.SVGProps<SVGSVGElement>>
  const pixels = sizeMap[size]
  return (
    <Component
      width={pixels}
      height={pixels}
      strokeWidth={size === 'xs' ? 1.5 : 1.75}
      className={className}
    />
  )
}
```

Usage: `<Icon name="Search" size="sm" />`.
