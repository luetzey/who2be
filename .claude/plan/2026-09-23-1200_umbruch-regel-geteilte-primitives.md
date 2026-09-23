# Umbruch-Regel in den geteilten Primitives (EntityCard-description + DetailHeader-h1)

Karte: t_126558ba · Branch: `who2be/t_126558ba-umbruch-regel-in-den-geteilten-primitive`
Basis: `origin/main` @ 9a05a4e8 · PR-Contract: `luetzey/who2be`

## Ziel

Lange Bezeichner ohne Trennstellen laufen bei 320px in den beiden geteilten
Primitives unter `apps/web/src/components/data/` ueber den Rand. Beide
Textknoten bekommen `break-words` (= `overflow-wrap: break-word`).

## Entschiedene Weiche (PM, 2026-09-23) — nicht neu verhandelt

Option A: `break-words` am Primitive. Kein `line-clamp` (versteckt Inhalt in
dreizehn Domaenen ohne deren Entscheidung), kein „je Domaene regelt es selbst"
(dreizehnmal dieselbe Frage, Pattern-Drift). `break-words` statt `break-all`,
weil es Freitext-/Namensslots sind, keine Mono-Identifier — dieselbe
Unterscheidung wie im #562-Review fuer die Badges.

## Befund am Baum (gegengelesen, nicht neu analysiert)

- `EntityCard.tsx:109` — `<p className="text-sm text-muted-foreground">`
  (Symbol `CardBody`). Elternkette bereits korrekt: `:96`
  `flex min-w-0 flex-1 flex-col gap-2`.
- `DetailHeader.tsx:60` — `<h1 className="text-2xl font-semibold tracking-tight">`.
  Elternkette bereits korrekt: `:56` `flex min-w-0 gap-4`, `:58` `min-w-0`.

Es fehlt nur die Umbruch-Regel am Textknoten selbst.

## Schritte

1. Plan ablegen (diese Datei).
2. **RED**: je ein Test pro Primitive, der die Umbruch-Klasse am jeweiligen
   Textknoten assertiert — kein Snapshot.
   - `EntityCard.test.tsx`: description-Absatz per `getByText` holen,
     `toHaveClass('break-words')`.
   - `DetailHeader.test.tsx`: `getByRole('heading', { level: 1 })`,
     `toHaveClass('break-words')`.
   RED-Commit separat, SHA im Handoff.
3. **GREEN**: je genau eine Klasse am bestehenden Element. Keine Struktur-,
   Prop- oder Slot-Aenderung.
4. Changelog-Fragment unter `changelog.d/` (`*.fixed.md`).
5. DoD web-seitig vollstaendig fahren (lint, `npx tsc -b`, `test:coverage` inkl.
   Skip-Budget, build, license:check, i18n:check) plus
   `uv run python scripts/check_code_refs.py .` und
   `scripts/changelog_fragments.py check`.
6. Push, PR oeffnen, `all-green` am exakten Head-SHA pruefen. Kein Merge.

## Grenzen

- Kein `line-clamp`, keine Hoehenbegrenzung, keine Truncation.
- Keine Aenderung an `components/ui/*`, keine Domaene unter `features/*`.
- Bricht ein Test in einer fremden Domaene: **nicht** anpassen — im Handoff
  melden, im Zweifel `needs_input` blocken.
- Kein Merge, kein Push auf main.

## Verifikations-Log

Basis: `origin/main` @ 9a05a4e8 · Node 22.23.2 (Pflicht nach CONTRIBUTING.md)

- **RED** @ `d647db76`: `vitest run src/components/data/{EntityCard,DetailHeader}.test.tsx`
  → 2 failed | 7 passed. Assertions wie erwartet:
  h1 = `text-2xl font-semibold tracking-tight`, p = `text-sm text-muted-foreground`.
- **GREEN** @ `052d2630`: dieselben zwei Dateien → 9 passed (2 files).
- `npm run lint` → exit 0, **0 errors**, 67 Warnungen (Altbestand, keine in den
  beiden geaenderten Dateien, insb. keine `tailwindcss/classnames-order`).
- `npx tsc -b` → exit 0.
- `npm run test:coverage` (mit JUnit) → exit 0, **1254 passed | 0 skipped**,
  200 Test-Files. **Keine fremde Domaene rot** — keine Anpassung fremder Tests.
  Coverage: Statements 87.32 %, Branches 81.33 %, Functions 82.72 %, Lines 88.4 %.
- `scripts/ci/assert_skips_within_budget.py junit-web.xml` → exit 0
  (0 uebersprungen, Budget 0/0).
- `npm run build` → exit 0.
- `npm run license:check` → exit 0.
- `npm run i18n:check` → exit 0 (174 bekannte Waisen aus der Baseline).
- `uv run python scripts/check_code_refs.py .` → exit 0 (0 error).
- `uv run python scripts/changelog_fragments.py check` → exit 0, Fragment
  `primitives-break-words.fixed.md` als `### Fixed` erkannt.
- `... guard --base origin/main` → exit 0 (CHANGELOG.md unberuehrt).
- Grenzen: `git diff origin/main --name-only -- apps/web/src/components/ui
  apps/web/src/features CHANGELOG.md` ist leer. Diff gesamt: 4 Dateien,
  32 insertions / 2 deletions — davon je eine Klasse Produktivcode.

