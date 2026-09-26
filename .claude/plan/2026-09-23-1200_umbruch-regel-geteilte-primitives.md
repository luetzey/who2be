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

## Runde 2 — Nachbesserung nach Review (Blocker 1)

Der Reviewer hat nachgemessen: `break-words` allein loest das Kartenziel fuer
`DetailHeader` **nicht**. Die H1 ist direktes Kind der Flex-Zeile
(`DetailHeader.tsx:59`) und hat als Flex-Item `min-width: auto`; sie blaeht sich
auf die ungebrochene Wortbreite auf, bevor `overflow-wrap` greifen kann. Das
`min-w-0` auf Zeile 58 sitzt eine Ebene **ueber** dem Flex-Container.

### Eigene Messung (Chromium, 320 px Viewport, Nachbau der exakten Klassenkette)

Titel `supercalifragilisticexpialidocious-mcp-server-produktion`, H1-Breite:

| Variante | Breite | Ueberlauf ueber den Rahmen |
|---|---|---|
| `break-words` (Stand Runde 1) | 365,8 px | **+134,8 px** |
| `break-words` + `min-w-0` **an der H1** | 206,0 px | kein Ueberlauf (−25,0 px) |
| `break-words` + `min-w-0` an der **Flex-Zeile** (Z. 59) | 365,8 px | **+134,8 px** |
| `min-w-0` an der H1, Titel ganz ohne Trennstelle | 206,0 px | kein Ueberlauf |

Damit ist die Stellenwahl **gemessen, nicht angenommen**: `min-w-0` an der
Flex-Zeile wirkt nicht — nur `min-w-0` an der H1 selbst. Die vom Reviewer
angebotene Alternative faellt damit aus; die Badges bleiben durch ihre eigenen
Klassen (`max-w-full break-all` aus #566) geschuetzt.

### Umsetzung

- **RED** @ `6bc7f845`: `DetailHeader.test.tsx` prueft jetzt **beide** tragenden
  Klassen (`toHaveClass('break-words', 'min-w-0')`) → 1 failed | 2 passed,
  received `text-2xl font-semibold tracking-tight break-words`. jsdom rechnet
  kein Layout; die Klassen-Assertion ueber beide Klassen ist die verfuegbare
  Grenze, der Layout-Nachweis steht in der Tabelle oben.
- **GREEN**: `min-w-0` an `DetailHeader.tsx:60` ergaenzt — eine Klasse am
  bestehenden Element, kein Strukturumbau, keine neuen Props (AK 2).
  `vitest run src/components/data/` → 62 passed (17 files).
- DoD Runde 2 komplett neu gefahren (Node 22.23.2): `lint` exit 0 / 0 errors
  (keine `classnames-order`-Warnung an der neuen Klassenreihenfolge
  `min-w-0 text-2xl font-semibold tracking-tight break-words`) · `tsc -b` exit 0 ·
  `test:coverage` exit 0, **1254 passed | 0 skipped**, 200 Files, 87,33 % stmts ·
  `build` exit 0 · `license:check` exit 0 · `i18n:check` exit 0 ·
  `check_code_refs.py` exit 0 · `changelog_fragments.py check` exit 0.
- Scope-Guard gegen `origin/main...HEAD`: `components/ui`, `features/`,
  `CHANGELOG.md` unberuehrt.

### Fuer @pm — Vorab-Analyse im Kartentext war teilweise falsch

Der Kartenabsatz „Kontext, schon nachgemessen" behauptet, die Elternketten
beider Primitives seien korrekt und es fehle „nur die Umbruch-Regel am
Textknoten". Fuer `EntityCard` stimmt das (`flex min-w-0 flex-1 flex-col` sitzt
direkt ueber dem `<p>`, das `<p>` ist Block-Kind, kein Flex-Item). Fuer
`DetailHeader` ist es messbar falsch: das `min-w-0` liegt eine Ebene zu hoch.
Der Befund stammt aus dem Review von t_1ca8a551 (#562/PR #595) und wird sonst
in weitere Karten weitergereicht.

