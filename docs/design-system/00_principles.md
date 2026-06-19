# 00 — Principles

Seven beliefs that drive every visual and interaction decision in RADAR. When two options conflict, the principle higher on this list wins.

---

## 1. Show your work

The user must always see what the system is doing and where the data came from. We do not hide processing behind black-box loaders. We do not display findings without citing sources. Trust comes from transparency, not polish.

**In practice:** Live logs during analysis. Source pills on every claim. Confidence scores when uncertain. Cite domains, not just facts.

---

## 2. Density with breathing room

VCs read 50-line tables for a living. We optimize for information density first, comfort second. But density without rhythm is noise — we still respect a grid, breathe between sections, and use whitespace as a structural element.

**In practice:** 4px base grid. Tight data rows (8–12px gap). Generous panel padding (24–32px). Tabular numbers always.

---

## 3. Operational, not marketing

The UI should feel like a tool an analyst opens at 9am, not a landing page a marketer ships. Restraint signals seriousness. We avoid: gradients on surfaces, drop shadows for decoration, illustrations, particle effects, 3D, parallax.

**In practice:** Square-ish corners (2–4px radius max). Solid surfaces. Functional motion only. Mono font for data/IDs. Status indicators everywhere (version, classification, operational state).

---

## 4. Motion conveys process

Animation exists to communicate state change or causality. Decorative motion is forbidden. When something animates, the user should be able to answer: "what did the system just do?"

**In practice:** Status dots pulse to mean "live." Text types on to mean "incoming data." Panels morph to mean "transformed, not replaced." Easing `cubic-bezier(0.2, 0.8, 0.2, 1)` — quick start, soft land.

---

## 5. Classify everything

Every screen carries metadata about its own state: version, system status, classification, time. Borrow the visual vocabulary of intelligence agencies and trading terminals — it instantly signals "operational software" to the audience we target.

**In practice:** Top-bar status (`SYSTEM: OPERATIONAL` · `v0.3.1` · `INTERNAL`). Phase classification chips. Timestamps on log lines. Provenance metadata on every data point.

---

## 6. Dark by default, not by trend

RADAR is dark because analysts work long hours and dense data is easier to scan on dark. Not because dark mode is trendy. Light mode is a future consideration, never a v0 priority.

**In practice:** Single theme. Deep near-black background (`#0a0a0f`). Elevated panels one step lighter. No "auto" mode.

---

## 7. Mono for data, grotesk for prose

Two typefaces, one role each.

**JetBrains Mono** — IDs, domains, URLs, code, timestamps, status text, numbers in data tables, source pills. Anything machine-emitted.

**Inter** (or equivalent humanist sans) — headlines, body prose, button labels, prose microcopy. Anything human-written.

No serifs. No third typeface. No display fonts. Tabular numerals enabled on both.

---

## Anti-principles (what we explicitly reject)

- Pleasant-looking onboarding flows with cartoons or illustrations.
- "Wow" animations that don't communicate state (sparkles, confetti, ease-out-bounce).
- Glassmorphism, neumorphism, or any current frosted/blurred trend.
- Hiding loading time behind generic spinners.
- Decorative gradients on surfaces or text.
- Pill-shaped buttons or super-rounded corners (consumer cue).
- Emojis in product UI. (Acceptable in docs and team messages, never in product.)
