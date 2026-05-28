# Radar — Journal de bord

> Daily ritual (10 min, le matin). 3 questions max. Pas de prose.
> Format: date ISO, 3 bullets. Plus récent en haut.

---

## 2026-05-28

- **Shipped**: refresh-recovery scan — run_id-keyed progress cache, `GET /scan/status`, localStorage restore + polling. 3 commits clean, smoke test 12/12 green.
- **Security**: 2 blockers caught in self-review and fixed pre-merge — `_validate_run_id` regex (path traversal) + `@limiter.exempt` on `/scan/status` (polling would have hit 429 after 20s).
- **NOW**: Manual E2E — refresh à 3 moments (mid-discover, mid-enrich, post-completion) avant de merger.

---

## 2026-05-17 (J1)

- **Shipped hier**: rien — premier jour de méthodo PM.
- **Blocker actuel**: pipeline jamais run end-to-end. Risque #1 du projet.
- **NOW aujourd'hui**: S0.1 — smoke test Phase 1 (`pipeline.understand` sur doctolib.fr).

---
