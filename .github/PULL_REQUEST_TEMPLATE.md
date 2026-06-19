## What & why

Short description of the change and the motivation.

## Type

- [ ] `feat` — new feature
- [ ] `fix` — bug or data-quality fix
- [ ] `chore` — tooling, CI, deps (no app logic)
- [ ] `docs` — documentation only
- [ ] `test` — tests / evals

## Checklist

- [ ] Branch follows naming convention (`feature/`, `fix/`, `chore/`, `docs/`)
- [ ] Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
- [ ] Branched off latest `main` — not pushing to `main` directly
- [ ] CI is green (`lint-and-smoke` + unit tests)
- [ ] If a Pydantic model changed, the matching frontend data shape changed in this PR
- [ ] If pipeline phases / Linkup endpoints / models / budget guards changed, `docs/Learning/ARCHITECTURE.md` is updated
- [ ] `STATUS.yaml` / `CLAUDE.md` updated if pipeline logic changed
- [ ] No secrets, `.env`, or client data committed

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full rules.
