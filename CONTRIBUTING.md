# Contributing to Who2Be

Thank you for your interest in Who2Be! This document describes the
development workflow and the conventions for contributions.

## Contributor License Agreement (CLA)

> **Not yet active.** The repository is public, but the CLA Assistant is
> still being set up. Until the signing link below is live, we cannot
> accept external pull requests — please open an issue instead, so your
> idea is on record and we can pick it up once the CLA is in place.

By submitting a contribution you agree to the terms of the Contributor
License Agreement (CLA). The CLA grants the copyright holder (currently
**Yannick Lützenburg**, with the right to transfer to a legal successor)
the rights required to publish your contribution under the project license
and to relicense it in the future.

<!-- CLA-LINK: replace the line below with the cla-assistant.io signing
     link once the app is installed (tracked in issue #338, O3). -->

**Signing link:** _pending — see [issue #338](https://github.com/luetzey/who2be/issues/338)._

Signing happens once, automatically, on your first pull request: the CLA
Assistant bot comments on the PR with a link, and your PR is unblocked as
soon as you accept.

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

A pull request that touches only documentation (`.claude/**`, `docs/**`,
root-level Markdown) skips the four heavy CI jobs (`python`, `web`,
`compose-smoke`, `e2e`) — each still reports a check status ("skipped"), so
required checks are unaffected.

For bugfixes, write a reproducing, failing test first, then fix. Fix the
cause, not the symptom; sketch larger changes as a plan first.

## Security

Please do not report security-relevant findings as public issues — use the
process described in [`SECURITY.md`](SECURITY.md) instead.
