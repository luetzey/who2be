# Phase E Web T2: Begriffe Hub und Melden

Karte t_7351ee46 · Spec `phase-e-web-neuschnitt-2026-10.md` §1, §7.1 Zeile T2

## Ziel

DE-Werte im Feedback-Hub und beim Melden: Fall → Rückmeldung (A4a). Keys,
Code und EN bleiben (N3 a).

## Geänderte Werte (de.json)

- `feedback.overview.tabs.cases` Fälle → Rückmeldungen
- `feedback.overview.tabs.myCases` Meine Fälle → Meine Rückmeldungen
- `feedback.overview.signalsDescription` „… meldest du als Fall“ → „… gibst du eine Rückmeldung“
- `feedback.cases.report.title` / `.submit` Fall melden → Rückmeldung geben
  (Hub-Kopf, Agent-Kopf, Dialog, Vollbildseite unter md)
- `feedback.cases.report.success` / `.successViewer` Erfolgstexte
- `feedback.cases.report.privacy`, `.noAgents` Fall → Rückmeldung
- `feedback.cases.list.description` / `.descriptionViewer`

## Bewusst nicht in T2 (gehört zu T3)

„Fall anlegen“ (`cases.report.create`), `notConvertible`, Muster-Texte,
Gedächtnis, Feedback-Detail („In Fall übernehmen“, „Zum Fall“).

## Dateien (Budget ≤ 8)

1 de.json · 2 FeedbackOverviewPage.test.tsx · 3 ReportCaseForm.test.tsx ·
4 FeedbackComposePages.test.tsx · 5 CaseList.test.tsx · 6 PatternList.test.tsx ·
7 Fragment = 7.

Abweichung von der Spec-Liste: `FeedbackOverviewPage.a11y.test.tsx` und
`FeedbackInbox.test.tsx` (beide „falls“) mussten nicht mit. Stattdessen
prüfen `CaseList.test.tsx` und `PatternList.test.tsx` den Knopf „Fall melden“
im Leerzustand und brechen deshalb mit. Mit 7 Dateien liegt das im Budget,
die Ausweichregel greift nicht.

## Verifikation

- `vitest run` (Node 22): 259 Dateien, 2236 Tests grün
- `tsc -b` ok, eslint ohne neue Befunde, Fragment-Check ok
- Fotos 1280/390 hell/dunkel: Hub editor, Hub viewer, Dialog/Vollbildseite, Agent-Kopf
