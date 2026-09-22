# CHANGELOG-Guard in CI + Alt-PR-Regel im Fragment-Verfahren

Karte: kanban t_b6b87106 · Branch `who2be/t_b6b87106-changelog-guard-in-ci-alt-pr-regel-im-fr`

## Ziel

Das P5-Fragment-Verfahren (#587) mechanisch durchsetzen: ein CI-Gate weist einen
direkten `CHANGELOG.md`-Eintrag in einem normalen PR ab; die fehlende Alt-PR-Regel
kommt in die Doku.

## Vorentschieden (PM, nicht neu aufgerollt)

- **E1** — eigener, ungegateter Job `changelog-guard` in `.github/workflows/ci.yml`
  (ein reiner CHANGELOG-PR faehrt `code=false`, ein Gate in `python`/`web` verfehlte
  den Zielfall strukturell).
- **E2** — Release-PR rein mechanisch am Diff: `CHANGELOG.md` darf sich nur aendern,
  wenn derselbe Diff mindestens eine Datei unter `changelog.d/` **loescht**
  (`changelog.d/README.md` zaehlt nicht).
- **E3** — Entscheidungslogik als Unterkommando `guard` in
  `scripts/changelog_fragments.py`, nicht als Workflow-Shell.
- **E4** — kein `npm run i18n:check` in CI; stattdessen ein klarstellender Satz in
  `CONTRIBUTING.md`.

## Schritte

1. `scripts/changelog_fragments.py`: reine Funktion `guard_violation(changed, deleted)`
   + `guard`-Unterkommando mit `--base <ref>`; Diff via `git merge-base`/`git diff`.
2. `.github/workflows/ci.yml`: Job `changelog-guard` (kein `needs`, kein `if`,
   `fetch-depth: 0`, SHA-gepinnte Actions, `uv`); bei `push` sauber uebersprungen.
3. `all-green`: den neuen Job in `needs` aufnehmen und mit `expect ... success`
   pruefen — sonst waere das Gate nicht Teil des einzigen Required Checks.
4. Tests in `scripts/tests/test_changelog_fragments.py` (Abweichung von der Karte,
   die `apps/api/tests/` nannte: die Tests des Moduls liegen seit #587 dort, der
   Pfad steht in `pyproject.toml` unter `testpaths`).
5. `CONTRIBUTING.md`: Alt-PR-Regel + Hinweis auf das Gate; i18n-Klarstellung (E4).
6. `changelog.d/README.md`: Alt-PR-Regel kurz + Gate-Hinweis.
7. Eigenes Fragment `changelog.d/changelog-guard.changed.md`.

## Verifikation

- `uv run python scripts/changelog_fragments.py guard --base origin/main` → Exit 0.
- Gegenprobe: Commit mit CHANGELOG-Hunk ohne geloeschtes Fragment → Exit 1
  (danach zuruecknehmen).
- `uv run ruff check . && uv run ruff format --check . && uv run mypy .`
- `WHO2BE_REQUIRE_DB=1 uv run pytest --cov --cov-fail-under=85` (DoD).

## Out of Scope

Kein Merge, kein Push auf main, kein Ruleset-Eintrag fuer den neuen Required Check
(Owner-Sache — aber: der Job haengt in `all-green`, das bereits Required ist).
