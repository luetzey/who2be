# D6c′ – mobile Melden-Seite `/feedback/cases/new` (Karte t_b3b7835c)

Basis: origin/main a0877f5d (D6c gemergt). Spec: Delta Phase D, S6 Absatz
„390 px“. Dazu die D6c-Review-Nits (b) Fall-Liste nach „Fall melden“ neu laden
und (d) Seitenkopf von FeedbackOverviewPage, solange die Rolle lädt.

## Dateien (Budget 7)
1. apps/web/src/components/cases/ReportCaseForm.tsx – Formular-Logik als
   `ReportCaseFlow` (Rahmen per Render-Prop: Dialog oder Seite), Auslöser unter
   `md` als Link auf die Route, `CasesChangedProvider` für Nit (b).
2. apps/web/src/features/feedback/pages/FeedbackComposePages.tsx – `ReportCasePage`.
3. apps/web/src/features/feedback/pages/FeedbackComposePages.test.tsx – Route,
   Absenden, Abbrechen (mit Verwerfen-Rückfrage), Deep-Link, Rechte (viewer).
4. apps/web/src/app/routes.tsx – `/w/:ws/feedback/cases/new` vor `:caseId`.
5. apps/web/src/features/feedback/pages/FeedbackOverviewPage.tsx – Provider um
   Kopf + Liste (Nit b), neutraler Inhalt solange `role === null` (Nit d).
6. apps/web/src/features/feedback/pages/FeedbackOverviewPage.test.tsx – Tests b/d.
7. changelog.d/t-b3b7835c-report-case-page.added.md

Keine neuen Texte: Titel/Intro/Knöpfe aus `cases.report.*`, Zurück aus
`common:actions.back` → de.json/en.json bleiben unberührt.

## Weichen (belegt)
- Zurück-Fluss wie Spec S6 „über state.from“ (Muster FeedbackComposePages):
  mit Herkunft `navigate(-1)` (Hub: zurück zur Fall-Liste, die beim Wieder-
  einhängen neu lädt), ohne Herkunft Ersatz durch `/feedback?tab=cases`.
- `?agent=<id>` mit Name im State → Agent fest (Lesewert); ohne Name
  (Deep-Link) → Auswahl vorbelegt, fällt auf leer, wenn der Agent nicht in
  `GET /agents` steht.
- Knopfleiste unten fixiert (`sticky bottom-0`), Textfelder wachsen bereits
  bis 60 svh (`Textarea autoGrow`).

## Stand
- [ ] Code  - [ ] Tests  - [ ] DoD  - [ ] Fotos  - [ ] e2e-mobile  - [ ] PR
