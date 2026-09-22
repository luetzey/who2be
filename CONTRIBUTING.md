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

## Referencing code

Never point at a code location with a bare `file.py:441`. Line numbers drift as
files grow, and a drifted pointer silently names the wrong code while still
looking valid. Every code reference carries a stable anchor — a commit SHA, a
symbol name, or both; a line number may be added but never counts as the
reference itself:

```text
conftest.py#_db_reachable            symbol anchor (the common case)
conftest.py@1a8f63b#_db_reachable    symbol + the commit it was measured at
apps/api/src/who2be_api/main.py@39dcdf4   SHA permalink (unnamed location)
```

Check references mechanically instead of by hand:

```bash
uv run python scripts/check_code_refs.py .          # whole repo
uv run python scripts/check_code_refs.py docs/ --json
```

Full convention, the stages the checker reports, and why old pointers are
deliberately left alone: [`docs/code-references.md`](docs/code-references.md).

## Changelog: ein Fragment, keine Sammeldatei

`CHANGELOG.md` wird **nicht** direkt bearbeitet. Jeder PR legt stattdessen
eine eigene kleine Datei unter [`changelog.d/`](changelog.d/) an.

**Warum:** Eine Sammeldatei, in die jeder PR an derselben Stelle schreibt, ist
genau die Datei, an der git still falsch zusammenführt — ohne Konfliktmarker,
ohne Warnung. In einer Welle dieses Repos stand danach ein Warnabsatz doppelt
im CHANGELOG. Schreibt jeder PR in eine eigene Datei, kann der Konflikt
strukturell nicht entstehen. Das Muster stammt von
[towncrier](https://github.com/twisted/towncrier) und ist bei Twisted, pytest,
pip und attrs in Produktion.

Ausdrücklich **nicht** verwendet wird `merge=union` in `.gitattributes`: die
git-Dokumentation warnt selbst davor, und es tauscht einen sichtbaren Konflikt
gegen einen stillen Fehler — die falsche Richtung.

### So geht es

Dateiname `changelog.d/<slug>.<typ>.md`; `<slug>` ist frei (sinnvoll: Branch-
oder PR-Bezug), `<typ>` eine Kategorie aus
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/): `added`, `changed`,
`deprecated`, `removed`, `fixed`, `security`.

Inhalt ist der Markdown-Listenpunkt, genau so wie er im CHANGELOG stehen soll —
mit führendem `- `, Folgeabsätze um zwei Leerzeichen eingerückt:

```markdown
<!-- changelog.d/oauth-issuer.fixed.md -->
- Remote-MCP-Connectors können sich wieder anmelden, wenn der OAuth-Issuer ein
  blanker Origin ist.

  Beide Dokumente führen jetzt die URL-Normalform mit Schrägstrich, die jeder
  URL-Parser unangetastet lässt.
```

```bash
uv run python scripts/changelog_fragments.py check                # Form prüfen
uv run python scripts/changelog_fragments.py collect --dry-run    # Vorschau
uv run python scripts/changelog_fragments.py collect              # übernehmen
```

`collect` trägt die Fragmente in die `## [Unreleased]`-Sektion ein und löscht
sie — das passiert **beim Release**, nicht in jedem PR. Bestehende
CHANGELOG-Einträge bleiben unberührt; das Verfahren gilt ab jetzt.

### Alt-PRs aus der Zeit vor dem Verfahren

Ein offener PR, der noch direkt in `CHANGELOG.md` schreibt, **verwirft seinen
CHANGELOG-Hunk und legt denselben Text wortgleich als Fragment ab** — nicht
umformuliert, nicht gekürzt, damit beim Release derselbe Eintrag entsteht, den
der PR gemeint hat.

CI erzwingt das: der Job `changelog-guard` in
[`.github/workflows/ci.yml`](.github/workflows/ci.yml) weist jeden PR ab, der
`CHANGELOG.md` ändert, ohne dabei mindestens ein Fragment unter `changelog.d/`
zu löschen — die Signatur eines `collect`-Laufs beim Release. Lokal nachprüfen:

```bash
uv run python scripts/changelog_fragments.py guard --base origin/main
```

## i18n: die Locale-Dateien prüfen lassen

`de.json` und `en.json` sind aus demselben Grund gefährdet wie der CHANGELOG,
nur lässt sich der Namensraum nicht auf Fragmente aufteilen. Nach demselben
Fehlmerge standen dort `auth.signup.captcha` und `auth.captcha` nebeneinander —
zwei konkurrierende Schlüssel, einer davon tot. Statt einer Umstrukturierung
gibt es deshalb eine Prüfung:

```bash
cd apps/web && npm run i18n:check
```

Sie prüft Schlüsselgleichheit zwischen beiden Locales, doppelt vergebene
Schlüssel im Rohtext (`JSON.parse` behält still den letzten) und Schlüssel, auf
die kein Code verweist.

**Das CI-Gate ist nicht dieses Kommando**, sondern `src/i18n/audit.test.ts`: die
Prüfungen laufen als Teil der Vitest-Suite unter `npm run test:coverage` im
CI-Job `web` und decken dort Parität, Duplikate, neue Waisen und das
Schrumpfen der Baseline ab. `npm run i18n:check` ist das lokale
Komfort-Kommando für den schnellen Blick nach einer Konfliktauflösung — es
zeigt zusätzlich die Baseline-Waisen, läuft aber ohne Suite. Ein zweiter
CI-Schritt dafür wäre redundante Laufzeit ohne zusätzliche Aussage.

Der Altbestand verwaister Schlüssel steht in
`src/i18n/orphan-baseline.json` — das Gate bricht nur bei **neuen** Waisen
(Ratchet, wie beim Coverage-Floor).

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
npm run test:coverage -- --reporter=default --reporter=junit \
  --outputFile.junit=junit-web.xml
python3 ../../scripts/ci/assert_skips_within_budget.py junit-web.xml
npm run build
npm run license:check   # OSS license gate (ADR-0033)
```

The skip budget applies to **both** stacks. On the web side it is attached to
the coverage step only — never to `npm run test:a11y`. That step runs the full
suite with `--testNamePattern a11y` and Vitest reports every filtered-out test
as `skipped`, so it structurally shows four-digit skip counts while those same
tests pass in the coverage run a minute earlier. A gate there would be
permanently red for no reason.

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

**Did you touch documentation, plans, issues or cards that cite code?** Then
the code references are verified by the checker, not by hand — a run that
re-measures pointers manually is not a DoD run:

```bash
uv run python scripts/check_code_refs.py .   # must exit 0
```

`legacy` findings (pre-existing bare `file:line` pointers) are reported but do
not fail the run; an `error` does. See
[`docs/code-references.md`](docs/code-references.md).

A pull request that touches only documentation (`.claude/**`, `docs/**`,
root-level Markdown) skips the four heavy CI jobs (`python`, `web`,
`compose-smoke`, `e2e`) — each still reports a check status ("skipped"), so
required checks are unaffected.

For bugfixes, write a reproducing, failing test first, then fix. Fix the
cause, not the symptom; sketch larger changes as a plan first.

### After resolving a conflict: read the net diff

Nach **jeder** Konfliktauflösung — Merge, Rebase oder Cherry-pick — wird der
Nettodiff des Ergebnisses gelesen. Das Ausbleiben von Konfliktmarkern ist
**kein** Beleg dafür, dass das Ergebnis stimmt: git führt messbar oft still
falsch zusammen, ohne Marker und ohne Warnung (die gemessene Grundrate liegt
bei rund 3 %, ASE 2024, 6045 Merge-Szenarien). Die drei Fehlmerges dieses Repos
— ein doppelter Warnabsatz im CHANGELOG und zwei konkurrierende i18n-Schlüssel
— trugen alle keinen einzigen Konfliktmarker.

**Das Verfahren, das sie tatsächlich gefunden hat, war der
Cherry-pick-Vergleich:** dieselbe Änderung unabhängig auf den Zielstand
cherry-gepickt und die beiden Bäume gegeneinander gehalten. Weichen sie ab, hat
der Merge etwas anderes getan als die Änderung selbst.

```bash
# 1. Der Nettodiff des Ergebnisses gegen den Zielstand — was ist WIRKLICH neu?
git diff origin/main...HEAD

# 2. Gegenprobe über einen unabhängig erzeugten Baum:
git switch --detach origin/main
git cherry-pick <commit>…            # dieselben Änderungen, anderer Weg
git diff HEAD <merge-ergebnis>       # leer = identisch, sonst hinsehen

# Mechanische Vorabprobe, ob überhaupt ein Konflikt entstünde
# (Exit 0 = sauber, 1 = Konflikt), ohne Working Tree und Index anzufassen:
git merge-tree --write-tree origin/main HEAD
```

Sammeldateien verdienen dabei besondere Aufmerksamkeit: `CHANGELOG.md` (siehe
Fragment-Verfahren oben) sowie `de.json`/`en.json` — für letztere ist
`npm run i18n:check` die schnelle Gegenprobe.

Nicht verwendet werden **`merge=union`** (verwandelt einen sichtbaren Konflikt
in einen stillen Fehler) und **`--ignore-space-change` / `-Xignore-all-space`**
im Merge-Pfad (senkt die Konfliktzahl um 5 %, erhöht die stillen Fehlmerges um
10 % — in Python und YAML mit bedeutungstragender Einrückung besonders
gefährlich).

## Security

Please do not report security-relevant findings as public issues — use the
process described in [`SECURITY.md`](SECURITY.md) instead.
