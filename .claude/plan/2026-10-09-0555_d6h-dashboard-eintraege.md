# D6h: Dashboard-Einträge „Muster“ und „offene Fälle“

Karte t_d30e793e · ADR-0053 D6h · Delta-Spec Phase D „Dashboard (D6h, Spec §10)“

## Outcome

Fertig heisst: editor und admin sehen im Band „Braucht jetzt deine
Aufmerksamkeit“ zusätzlich

- „{{count}} Muster“ (`brand`, Aktion „Ansehen“ → `/feedback?tab=patterns`),
  Zahl = Länge von `patterns` aus `GET /patterns`;
- „{{count}} offene Fälle“ (`brand`, Aktion „Einordnen“ → `/feedback?tab=cases`),
  Zahl = `open` + `reopened` aus `GET /cases/counts`. Die Fall-Liste wird nie
  zum Zählen geladen.

Jeder Eintrag erscheint nur bei count > 0. viewer (und eine noch unbekannte
Rolle) lösen keinen der beiden Aufrufe aus und sehen keinen Eintrag.

## Dateien (6)

1. `apps/web/src/features/dashboard/pages/DashboardPage.tsx`
2. `apps/web/src/features/dashboard/pages/DashboardPage.test.tsx`
3. `apps/web/src/features/dashboard/pages/DashboardPage.a11y.test.tsx` (axe mit beiden Einträgen)
4. `apps/web/src/i18n/locales/de.json`
5. `apps/web/src/i18n/locales/en.json`
6. `changelog.d/t-d30e793e-dashboard-patterns-cases.added.md`

## Entscheidungen

- „nur für editor“ heisst wie im Hub (`canTriage`): Rolle bekannt und nicht
  viewer, also editor und admin. `GET /patterns` erlaubt editor ab (6.5).
- Zwei getrennte Effekte: Scheitert einer, bleibt der andere Eintrag und das
  übrige Dashboard stehen. Fehler oder Laden → `null` → kein Eintrag.
- „Alles erledigt“ erscheint für editor nur, wenn beide Zahlen geladen und 0
  sind (dieselbe Regel wie C5a-2: eine unbelegte Zahl behauptet nichts). Für
  viewer zählen die Einträge nicht.
- Reihenfolge im Band: Reviews, Gedächtnis-Freigabe, Muster, offene Fälle,
  System-Prompts. Die Lernschleifen-Einträge stehen beieinander.
- Neue Einträge der Lernschleife im Band: Freigabe (C5a), Muster, offene
  Fälle — drei von höchstens vier. Ein Sammel-Link entfällt deshalb.
- Icons wie die Hub-Tabs: `Repeat` (Muster), `MessageSquareWarning` (Fälle).
- Plural mit `_one`/`_other` in DE und EN (DE-Singular „1 offener Fall“,
  EN „1 pattern“/„1 open case“).

## Verifikation

`npx tsc -b`, `npm run lint`, `npx vitest run src/features/dashboard`,
`npm run test:coverage` (inkl. i18n-Audit). Gegenprobe: neue Tests gegen
`DashboardPage.tsx` von origin/main rot. Fotos 1280/390 hell/dunkel mit
`measure.json`.

## Ergebnis

- Web-DoD unter Node 22 grün: lint (0 Fehler), `tsc -b`, `test:coverage`
  253 Dateien / 2141 Tests, Skip-Budget 0, build, license:check.
- Gegenprobe gegen `DashboardPage.tsx` von origin/main: 7 der neuen Tests rot
  (beide Einträge editor/admin, Singular, Null-Fall, beide Fehlerfälle, axe);
  die zwei viewer/Rolle-unbekannt-Tests prüfen Abwesenheit und sind dort
  erwartungsgemäß grün.
- Fotos: 4 Dateien (Dashboard-Band, 1280/390 × hell/dunkel), measure alle
  scrollWidth == clientWidth.
