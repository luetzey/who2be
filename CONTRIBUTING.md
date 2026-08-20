# Contributing to Who2Be

Thank you for your interest in Who2Be! This document describes the
development workflow and the conventions for contributions.

## Contributor License Agreement (CLA)

> **Placeholder — becomes active with the public switch.**

By submitting a contribution you agree to the terms of the Contributor
License Agreement (CLA) once it is active. The CLA grants the copyright
holder (currently **Yannick Lützenburg**, with the right to transfer to a
legal successor) the rights required to publish your contribution under the
project license and to relicense it in the future.

The CLA link (CLA Assistant) will be added here as soon as the repository is
public. Until then, external contributions are not yet open.

## License

Who2Be is licensed under the
[Functional Source License 1.1 (Apache 2.0 Future)](LICENSE). Contributions
are accepted under the same license.

## Branch convention

- Feature branches: `feat/<short>`
- Bugfix branches: `fix/<short>`
- Cloud/web sessions (Claude Code) automatically use the `claude/` prefix.
- Always branch off `main`; never push directly to `main`.

### Sandbox / experiments

Quick, unfinished experiments live on local `sandbox/*` branches
**without remote tracking** — they are not pushed and do not run through CI.
As soon as something is presentable, it moves into the normal PR path as a
clean `feat/` or `fix/` branch (or by cherry-picking the relevant commits).
This keeps the public history tidy without losing solo-dev convenience.

## Commit convention

- [Conventional Commits](https://www.conventionalcommits.org/) (e.g.
  `feat: …`, `fix: …`, `docs: …`, `chore: …`).
- Meaningful commit messages; one PR per completed unit of work.
- Every PR needs at least **one** review.

## Definition of Done

Verify locally before every push (both stacks green). The test steps
deliberately run with the same coverage gates as CI (coverage ratchet):
**green locally = green in CI** — a test run without the coverage gate does
not satisfy the DoD.

**Python (uv workspace in the repo root):**

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest --cov --cov-fail-under=85
# OSS license gate (ADR-0033) — fail-closed against copyleft/AGPL:
uv run --with pip-licenses python -m piplicenses --partial-match \
  --fail-on "GPL;AGPL;LGPL;SSPL;CDDL;EPL;EUPL;OSL;CPL;NPL;Sleepycat;UNKNOWN"
```

**Web (in `apps/web/`):**

```bash
npm run lint
npx tsc --noEmit
npm run test:coverage
npm run build
npm run license:check   # OSS license gate (ADR-0033)
```

New dependency? Check its license first (mandatory scan, ADR-0033).
Permissive licenses (MIT, BSD, Apache-2.0, ISC, 0BSD) and MPL-2.0 are
allowed; GPL/AGPL/LGPL and other copyleft licenses break the gate.
Deliberate exceptions require an ADR addendum.

For bugfixes, write a reproducing, failing test first, then fix. Fix the
cause, not the symptom; sketch larger changes as a plan first.

## Security

Please do not report security-relevant findings as public issues — use the
process described in [`SECURITY.md`](SECURITY.md) instead.
