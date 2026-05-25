# Contributing to RADAR

## Branch naming

| Prefix   | When to use                   | Example                       |
|----------|-------------------------------|-------------------------------|
| `feature/` | New capability              | `feature/pricing-display`     |
| `fix/`   | Bug or data quality issue     | `fix/similarity-scores`       |
| `chore/` | CI, deps, tooling             | `chore/add-ruff-ci`           |
| `docs/`  | Docs only                     | `docs/update-architecture`    |

## Commit format — [Conventional Commits](https://www.conventionalcommits.org/)

```
type(scope): short description
```

| Type | When |
|------|------|
| `feat` | New feature |
| `fix` | Bug fix or data quality issue |
| `chore` | Tooling, CI, deps — no app logic |
| `docs` | Documentation only |
| `test` | Tests, evals |

Examples:
```
fix(transform): derive similarity from radar scores
feat(frontend): add pricing tiers panel
chore(ci): add ruff lint workflow
```

## PR rules

- [ ] Branch off latest `main` (`git pull` before `git checkout -b`)
- [ ] CI passes (`lint-and-smoke` check must be green)
- [ ] `STATUS.yaml` or `CLAUDE.md` updated if pipeline logic changed
- [ ] No live Linkup API calls in tests (budget cap: €5/day)

## Local dev setup

```bash
cd RADAR/radar/backend
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
```

## Running evals

```bash
# Zero-cost import smoke:
python -m utils.dedup
python -m utils.geocoding

# Full E2E (costs ~€0.65 — uses cache on second run):
python evals/eval_e2e_simple.py indy.fr
```

## Branch protection (GitHub settings)

`main` requires:
- Pull request before merging
- Status check: `lint-and-smoke` must pass
- Include administrators: ON
