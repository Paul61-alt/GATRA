# Design Brief — Competitor Detail Screen (`CompanyScreen`) redesign

> Author: frontenddesigner pass · Audience: CTO/implementer · Date: 2026-05-31
> Target file: `radar/frontend-prototype/screens-company.jsx` (+ `styles.css`, reuse from `screens-overview-v2.jsx` & `components.jsx`)

---

## 1. Context & problem

The per-competitor detail screen (`CompanyScreen`, opened via `openCompany(id)` → dynamic `company:<id>` tab) is visually **much poorer** than the subject's `OverviewScreenV2`. The subject gets a rich, sectioned dashboard (HeroRibbon, FundingTimelineCard, TeamCard, CustomersStrip, InvestorsStrip, FootprintCard, NewsMomentumCard). The competitor gets a flat stack: header → stat strip → pricing/positioning → funding history → LinkedIn feed → feature coverage.

The new "Recent LinkedIn activity" card works but reads as a plain text list — "ça donne pas envie." User wants: **logos, richer link-preview style, and clean sections like the 'understand' (overview-v2) part.**

**Root cause:** `CompanyScreen` does not reuse the polished v2 section components. The single highest-leverage move is to **unify the competitor detail with the v2 card system**, then elevate the LinkedIn feed into a proper post-preview card.

**Intended outcome:** a competitor detail page that feels like the same product as the subject overview — sectioned, logo-rich, with a LinkedIn activity card that looks like a real social unfurl, not a bullet list.

---

## 2. Aesthetic direction — KEEP & ELEVATE (do not reinvent)

RADAR's identity is a **warm editorial research report**: cream canvas (`--bg #faf9f7`), near-black ink (`--fg #14110d`), single terracotta accent (`--accent #b34a1f`), Roboto Slab (display) + Roboto (body) + Roboto Mono (labels/data). Generous whitespace, hairline borders (`--border-dim`), flat cards with `--shadow-sm`.

Rule: **no new palette, no LinkedIn-blue, no second accent.** The terracotta is the only accent. Elevation comes from logos, spacing rhythm, and one motion moment — not color.

---

## 3. Reference inspiration (Mobbin)

| Pattern | Source | What to steal |
|---|---|---|
| **Section-card profile** | Wellfound / Notion profile | Funding as labelled stat-boxes (Valuation · Funded over · Latest round); right-rail "About" with logo, website, locations, market tags. Clean section headers with "View all →". |
| **Link-preview / activity card** | Current (post feed) | Card = small media block + bold title + 2-line excerpt + footer row (avatar + author + relative time + tag). This is the model for LinkedIn posts. |
| **Post feed row** | Peerlist / Binance Square / Threads | Avatar (logo) left, author bold + handle + timestamp on one line, body below, subtle action affordance right. Tight vertical rhythm. |

The LinkedIn card = **Current's link-preview** body + **Peerlist's** avatar/author/time header, rendered in RADAR's warm palette.

---

## 4. Information architecture — section stack (top→bottom)

Reorder `CompanyScreen` to mirror the subject's narrative, reusing v2 components:

1. **Hero header** (keep, polish) — `LogoMark` lg + name + `ThreatTag`/SUBJECT + tagline + category·subcategory; right = `LandingScreenshot`.
2. **At-a-glance stat strip** (keep) — Founded · HQ · Employees · Total raised · Similarity.
3. **Two-column**: Positioning (left) · Pricing (right) (keep).
4. **Recent LinkedIn activity** ← REDESIGN (section 5). Promote it higher — it's the freshest signal.
5. **Funding history** — replace bespoke bar list with **`FundingTimelineCard`** (reuse from v2) for consistency.
6. **Key people** — add **`TeamCard`** (reuse v2). Currently `key_people` is fetched but never rendered on the competitor screen → free win, and gives founder logos/avatars.
7. **Customers / Investors** — reuse **`CustomersStrip`** + **`InvestorsStrip`** (logo chips).
8. **Feature coverage** (keep).
9. **Footprint/offices** — optional **`FootprintCard`** if geo data present.

> The big lift = items 5–7: stop hand-rolling and reuse the v2 cards already built for the subject. Instant parity.

---

## 5. THE LINKEDIN CARD — detailed spec (primary request)

### 5.1 Data reality (constraint)
Linkup returns **no post images** (validated 0/5, eval round 6). Fields available per post: `date`, `author`, `excerpt` (≤300c, capped), `imageUrl` (almost always null), `sourceUrl`. So "preview with logos" must be built **without** relying on a post hero image.

### 5.2 Solution — logo-driven unfurl card
Each post = a horizontal card:

```
┌────────────────────────────────────────────────────────────┐
│ ▌ [LOGO]  Maki People · in            MAY '26     view post ↗│   ← header row
│ ▌         "Dans un marché en pleine transformation,         │   ← excerpt
│ ▌          comment concilier volume, exigence…"             │
│ ▌         🔗 linkedin.com/posts/…                           │   ← source chip
└────────────────────────────────────────────────────────────┘
   ↑ terracotta accent bar (hover)
```

- **Avatar = `LogoMark`** (`size="sm"`, `domain={company.domain}`, `name={p.author}`). Author is the company → its favicon logo. For a person-author with no domain, LogoMark falls back to initials. **This is the "logos" the user asked for.**
- **Header row:** logo · author (semibold) · tiny `in` LinkedIn monogram chip (fg-4, not blue) · pushed right: `fmtDate(p.date)` mono + `view post ↗`.
- **Excerpt:** `_truncGraphemes(excerpt, 220)` (drop to ~2–3 lines so cards stay scannable; emoji-safe already). Serif-ish? No — keep body sans, `--fg-2`, line-height 1.6.
- **Source chip:** a faint pill showing the post host (`linkedin.com/posts/…` shortened) with a link glyph — the "unfurl" cue that replaces a missing OG image. Subtle, `--fg-4`, mono 10px.
- **Optional image:** IF `p.imageUrl` present, show a 64×64 rounded thumbnail left of the text (with `onError` hide). Rare, but free.
- **Whole card** is the link (`<a href={sourceUrl} target="_blank" rel="noopener noreferrer">`).

### 5.3 Card container
- Section uses `card` + `card-h` (`<h3>Recent LinkedIn activity</h3>` + meta `Last 12 months · N posts` with the `in` monogram).
- Default show **3**, `+N more` toggle (already implemented; keep).
- Reuse the `.li-*` CSS classes already added in `styles.css` (extend, don't duplicate).

### 5.4 Motion
- Keep staggered reveal (`animation-delay: i*60ms`, `@keyframes li-reveal`) — already in place, respect `prefers-reduced-motion`.
- Hover: bg → `--bg-2`, left accent bar → `--accent`, `view post` → `--accent`. (Already in CSS.)

---

## 6. Logo strategy (reuse, don't build)
`LogoMark({name, domain, size})` in `components.jsx:397` already does favicon-by-domain (`t2.gstatic.com/faviconV2`) with initials fallback + `onError`. Use it for:
- Post avatars (`size="sm"`).
- Customer/investor chips (via `CustomersStrip`/`InvestorsStrip`, already do this).
- Founder avatars in `TeamCard`.

No new logo fetching. If higher-res logos are wanted later, that's a separate `LogoMark` enhancement, out of scope here.

---

## 7. Technical notes for CTO

- **Biggest win, least code:** import & render the v2 cards (`FundingTimelineCard`, `TeamCard`, `CustomersStrip`, `InvestorsStrip`, `FootprintCard`) inside `CompanyScreen`. They take a single `subject`-shaped object — the competitor `c` already carries `fundingRounds`, `keyPeople`, `notable_customers`, `notable_investors`, etc. Verify field-name parity (camelCase vs snake) before wiring; `key_people`/`notable_customers` are snake-case in data.js.
- **LinkedIn card:** modify the existing block in `screens-company.jsx` (~line 264). Swap the plain author span for `<LogoMark size="sm" domain={c.domain} name={p.author} />`, add the source chip, drop excerpt truncation to ~220. Extend `.li-*` classes in `styles.css` (add `.li-source-chip`, `.li-head`).
- **Data already present:** `c.recentLinkedinPosts` (camelCase, both pipeline + demo paths). No backend change.
- **Hooks:** the show-all `useState` must stay above the `if (!c) return` early return (already fixed).
- **No build step:** prototype uses in-browser Babel; verify by hard-reload (Cmd+Shift+R) on the local server, not a tunnel (see env note: VSCode dev-tunnel prompts for a token — open `http://127.0.0.1:8077` in a real browser).

---

## 8. Out of scope / risks
- Real post OG images — Linkup doesn't provide; do not scrape (cost + 403 + expiring CDN URLs).
- Subject LinkedIn posts — `CompanyProfile` carries no `recent_linkedin_signals`; competitor-only for now.
- New color/brand — explicitly avoided; stay in RADAR's warm palette.
- Field-name mismatches between subject-shaped v2 cards and competitor objects are the main implementation risk — audit each reused card's expected props against a real competitor entry in `data.js` first.

---

## 9. Acceptance criteria
- Competitor detail visually matches the subject overview's section quality (same card system).
- LinkedIn card shows a company **logo** per post, author, date, a clean 2–3 line excerpt, a source chip, and links out.
- Empty-state: section hidden when no posts (keep).
- Emojis never split at truncation (keep grapheme-safe).
- Works on the warm theme with the single terracotta accent; no LinkedIn-blue.
