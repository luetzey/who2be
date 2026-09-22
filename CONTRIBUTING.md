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
WHO2BE_REQUIRE_DB=1 uv run pytest --cov --cov-fail-under=85 \
  --junitxml=junit-python.xml
python3 scripts/ci/assert_skips_within_budget.py junit-python.xml
# OSS license gate (ADR-0033) — fail-closed against copyleft/AGPL:
uv run --with pip-licenses python -m piplicenses --partial-match \
  --fail-on "GPL;AGPL;LGPL;SSPL;CDDL;EPL;EUPL;OSL;CPL;NPL;Sleepycat;UNKNOWN"
```

### A skipped test is not a passing test

`WHO2BE_REQUIRE_DB=1` turns a missing database into a **hard failure** instead
of a silent skip (`conftest.py`, ADR-0041). Without it, a machine with no
Postgres/Docker reports roughly *1507 passed, 485 skipped* and exits 0 — the
integration suite never ran. CI sets the variable in the `python` job, so a
local run without it is **not** equivalent to CI and does not satisfy the DoD.

Need a database locally? Either start the compose stack
(see [`docs/local-smoke.md`](docs/local-smoke.md)) or run with
`WHO2BE_TEST_TESTCONTAINERS=1` (requires Docker) to get an ephemeral Postgres.

`scripts/ci/assert_skips_within_budget.py` is the second line of defence: it
reads the JUnit XML and fails when tests were skipped for infrastructure
reasons (budget: **0** — in CI the database is a service container, so a skip
there means the setup is broken) or when other skips exceed
`--max-other-skips` (default **0**; raising it belongs in the PR with a
reason). Platform-conditional skips are the only category the budget is meant
to accommodate.

**Reporting test results:** any handoff, PR description, or review note that
quotes a test run must state **both** numbers — passed *and* skipped. "Tests
green" without the skip count is not evidence; it is exactly how a run whose
core never executed gets accepted.

**Web (in `apps/web/`):**

```bash
npm run lint
npx tsc -b
npm run test:coverage
npm run build
npm run license:check   # OSS license gate (ADR-0033)
```

**Node 22 is mandatory, not a recommendation.** The repo pins the major in
`.nvmrc`, `mise.toml` and `apps/web/package.json` (`engines.node`), matching
`node-version: 22` in `.github/workflows/ci.yml`. Run `mise install` (or
`nvm use` / `fnm use`) in the repo root before touching the web stack. On Node
25+ `npm run test:coverage` fails with ~135 red tests and writes no `coverage/`,
because Node enables Web Storage by default there and Vitest 4 then filters
jsdom's `window.localStorage` away (upstream
[vitest#8757](https://github.com/vitest-dev/vitest/issues/8757), fixed only in
Vitest 5 — no 4.1.x backport). CI stays green because it runs Node 22, so a
local failure on a newer Node is a toolchain mismatch, not a code defect.

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
