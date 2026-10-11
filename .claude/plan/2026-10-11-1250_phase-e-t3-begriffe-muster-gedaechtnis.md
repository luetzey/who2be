# Phase E Web T3: Begriffe Muster, Gedächtnis, Feedback-Detail

Karte t_7a6ee0d4 · Spec `phase-e-web-neuschnitt-2026-10.md` §1, §7.1 Zeile T3

## Ziel

Restliche DE-Werte mit „Fall/Fälle“ außerhalb von Liste/Detail/Hub (E5a, T2):
Fall → Rückmeldung (A4a). Keys, Code und EN bleiben (N3 a).

## Geänderte Werte (de.json)

- Feedback-Detail: `feedback.item.promote` „In Rückmeldung übernehmen“,
  `promoteHelp` („… gilt dann als erledigt“ — die Resolution heißt im UI „Erledigt“, §1 Abgrenzung)
- Dialog aus Herkunft: `feedback.cases.report.create` „Rückmeldung anlegen“,
  `report.error.notConvertible`
- Muster: `feedback.patterns.description`, `descriptionNoThreshold`,
  `vanishHint` („umgesetzt“ → „geändert“, Status addressed = Geändert),
  `kind.case.title/text`, `action.createCase/viewCases`, `emptyDescription`, `emptyNoData`
- Gedächtnis: `learning.entries.action.convert` „Rückmeldung daraus machen“,
  `action.toCase` „Zur Rückmeldung“, `entries.status.converted` +
  `history.event.converted` „Zur Rückmeldung geworden“, `kindIntro.lesson` +
  `autoPolicy.locked.lesson`
- Prüffall-Herkunft `learning.testCases.row.fromCase` „aus Rückmeldung {{id}}“
- Agent-Überblick Muster-Kachel `agents.overview.kpi.patternCase` „Rückmeldungen“

## Bewusst unverändert

- `feedback.patterns.builder.promptLesson/promptCase`: Text, den man dem
  Builder im Client einfügt; dessen Werkzeug heißt `report_case`, der Prompt
  bleibt bei der Werkzeugsprache.
- `learning.testCases.retire.question`, `form.help.input`: „Fall“ meint dort
  den Prüffall bzw. den realen Einsatzfall, nicht die Rückmeldung.

## Dateien (Budget ≤ 8)

1 de.json · 2 PatternList.test.tsx · 3 MemoryDetailSheet.test.tsx ·
4 FeedbackItemDetailPage.test.tsx · 5 ReportCaseForm.test.tsx · 6 Fragment = 6.

Abweichung: `MemoryPage.test.tsx` (Spec-Liste) bricht nicht („Lektion aus Fall 7.“
ist Testdatum). Dafür prüft `ReportCaseForm.test.tsx` den Knopf „Fall anlegen“
und `notConvertible`. Budget eingehalten, keine Ausweichregel nötig.

## Verifikation

- `vitest run` (Node 22): 259 Dateien, 2236 Tests grün
- lint/tsc/build, Fragment-Check
- Fotos 1280/390 hell/dunkel: Muster-Liste + Sheet, Gedächtnis-Sheet, Feedback-Detail + Dialog
