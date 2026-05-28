# Radar — Backlog

> Règles: WIP=1 dans NOW. NEXT max 5 stories ordonnées par risque/valeur. LATER = parking.
> Une story passe en NOW seulement quand la précédente est mergée + visible dans la démo.

---

## NOW (1 story max)

### S0.1 — Smoke test Phase 1 (understand)
- **But**: prouver que `pipeline/understand.py` tourne end-to-end sur une vraie URL.
- **Commande**: `cd RADAR/radar/backend && python -m pipeline.understand "https://doctolib.fr"`
- **DoD**:
  - [ ] Sortie = `CompanyProfile` JSON valide (name, HQ city/country, funding, markets)
  - [ ] Durée < 20s
  - [ ] Logs propres, pas de stacktrace
  - [ ] Coordonnées GPS absentes ici (Phase Nominatim séparée)
- **Estim**: ~30 min
- **Démarré**: 2026-05-17

---

## NEXT (max 5, ordonnées par risque)

1. **S0.2 — Smoke test Phase 2 (discover)** — 15 concurrents dédupliqués. ~30 min.
2. **S0.3 — Smoke test Phase 3 (enrich)** — 3 `CompetitorProfile` avec pricing + signaux. ~1h.
3. **S0.4 — End-to-end via FastAPI** — `uvicorn`, route hit, `RadarOutput` complet en < 90s. ~1-2h.
4. **S0.5 — End-to-end via frontend** — `npm run dev`, démo flow visible sur Doctolib. ~1-2h.
5. **S1.1 — Score de similarité 0-100** — badge "82% similar" sur chaque carte concurrent. ~3-4h.

---

## LATER (parking — pas avant NEXT vide)

### E1 — Phase 4 Synthèse
- S1.2 Threat level (High/Medium/Low) + filtre grid
- S1.3 Matrice features comparée (composant `<FeatureMatrix />`)
- S1.4 Radar chart positioning (5 axes)
- S1.5 Pricing tiers parsés (struct JSON, pas strings bruts)

### E2 — Demo hardening
- S2.1 Script `scripts/precompute_demo.py` (5 startups démo)
- S2.2 Fallback cache transparent si Linkup timeout
- S2.3 Loading states & ETA par phase
- S2.4 Error states gracieux + retry phase

### E3 — Polish frontend
- S3.1 Branding (logo, favicon, palette)
- S3.2 Empty state engageant
- S3.3 Animation entrée concurrents (stagger fade-in)
- S3.4 Map zoom auto sur bounding box
- S3.5 Bouton "Share this analysis" (URL slug → cache)

### E4 — Deploy (J-2 max)
- S4.1 Backend Railway/Render
- S4.2 Frontend Vercel
- S4.3 Smoke test prod end-to-end

### E5 — Refresh-recovery follow-ups (non-bloquants, post-démo)
- S5.1 Cap retry count dans `pollScanStatus` (loop infini si backend down)
- S5.2 Factoriser le dict progress (~11 sites de construction ad-hoc dans `main.py`)
- S5.3 Status endpoint renvoie `hasResult: true` au lieu du `result` complet → un GET séparé pour le payload (économie bande passante sur polling post-completion)
- S5.4 Assert/drop ligne `run_id = company_profile.pipeline_run_id` ([main.py:381](RADAR/radar/backend/main.py#L381)) — probablement redondant

---

## Done (chronologique, plus récent en haut)

- **2026-05-28** — Refresh-recovery scan (progress cache + status endpoint + localStorage restore + polling). Smoke test 12/12. 2 blockers sécurité corrigés (path traversal, rate-limit).

---

## Cut-line

**J-3 avant démo** = plus aucune nouvelle feature. Polish + fallbacks + pre-cache uniquement.
Toute story non-mergée à J-3 → LATER.
