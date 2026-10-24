# Doku-Drift Stufe 2: CI-Warnung „UI geändert, Hilfe nicht“

Karte: t_0d3f4203 (Owner-Entscheidung 2026-10-22, W-B1 = Warnung, keine Sperre).
Grundlage: Recherche `clients-und-doku-drift-2026-10.md` §6.1.

## Ziel (fertig heißt)

Ein PR, der nutzersichtbare Web-Pfade ändert, ohne `apps/web/src/help/**` zu
ändern, bekommt im Job `changes` eine GitHub-Annotation `warning` plus eine
Zeile im Job-Summary — außer die PR-Beschreibung trägt eine gültige Zeile
`Hilfe: n/a – <Grund>` mit Grund aus der festen Liste. Kein harter Block.

## Weichen (entschieden, mit Beleg)

- Ort: eigener Step im vorhandenen Job `changes` (ci.yml), Logik in
  `scripts/ci/help_drift.py` (stdlib only, wie `assert_skips_within_budget.py`),
  weil Workflow-Shell unter keinem Test läuft. Keine Fremd-Action.
- Step `continue-on-error: true`, Skript endet immer mit Exit 0: die Warnung
  darf `code=` und damit die schweren Jobs nie beeinflussen. `all-green`,
  Trigger, Permissions, Secrets unverändert.
- Pfadtabelle eng:
  - `apps/web/src/features/<f>/components/**` ohne Testdateien
    (`*.test.*`, `*.spec.*`, `__tests__/`).
  - `apps/web/src/i18n/locales/*.json`: nur Schlüssel, die in Basis UND Head
    existieren und deren Wert sich geändert hat. Neue und entfernte Schlüssel
    lösen nicht aus (Karte: „nur geänderte Werte, nicht neue Schlüssel“).
  - Hilfe-Pfad: `apps/web/src/help/**`.
- Grundliste fest: `intern`, `kein UI-Text`, `nur Tests`,
  `Folgekarte <id>` mit `<id>` = `t_<hex>` oder `#<nr>`.
- PR-Body kommt aus `github.event.pull_request.body` per `env:` (kein
  Template-Ausdruck in der Shell → keine Script-Injection). Grenze: eine
  nachträgliche Body-Änderung wirkt erst beim nächsten Push, weil der Trigger
  `edited` bewusst nicht ergänzt wird (würde die volle CI je Edit starten).
- `Hilfe: geändert` ohne Änderung unter `help/` → ebenfalls Warnung.
- HTML-Kommentare im Body werden vor dem Parsen entfernt (Template-Beispiele).

## Dateien (≤ 8)

1. `scripts/ci/help_drift.py` (neu)
2. `scripts/tests/test_help_drift.py` (neu)
3. `.github/workflows/ci.yml` (ein Step)
4. `.github/pull_request_template.md` (eine Zeile + Kommentar)
5. `CONTRIBUTING.md` (kurzer Abschnitt)
6. `changelog.d/help-drift-warning.added.md`
7. dieser Plan

## Verifikation

- `uv run pytest scripts/tests/test_help_drift.py scripts/tests/test_ci_all_green_matrix.py`
- `uv run ruff check . && uv run ruff format --check . && uv run mypy .`
- `uv run python scripts/changelog_fragments.py check`
- Test-PR: dieser PR selbst ändert keine UI → Summary „keine UI-Pfade“; die
  Warnung wird per lokalem Lauf gegen einen UI-Commit belegt.

## Fortschritt

- [x] Skript + Tests (27 Tests, scripts/tests gesamt 137 grün)
- [x] ci.yml-Step
- [x] Template, CONTRIBUTING, Changelog (STATE.md entfällt: seit #783 nicht
      mehr je PR gepflegt)
- [x] DoD lokal: ruff, format, mypy (639 Dateien), changelog check,
      all-green-Matrix 20/20
- [x] Kalibrierung gegen main: 2190cd92 (Connector-Baustein ohne Hilfe) →
      Warnung; 3e17d7ab, ebd3822c → still
- [ ] PR, CI grün
