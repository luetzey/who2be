# D6b – Feedback-Hub mit URL-Tabs und Fall-Liste (Karte t_149e2237)

Basis: origin/main 2789aa69 (D6b0 gemergt). Spec: Delta Phase D §0/S7/Barrierefreiheit,
Filter-Standard §3.2 (geht bei Filtern vor), PM-Entscheidungen der Karte.

## Dateien (Budget 8)
1. apps/web/src/features/feedback/components/CaseList.tsx (neu)
2. apps/web/src/features/feedback/components/CaseList.test.tsx (neu)
3. apps/web/src/features/feedback/pages/FeedbackOverviewPage.tsx
4. apps/web/src/features/feedback/pages/FeedbackOverviewPage.test.tsx
5. apps/web/src/features/feedback/pages/FeedbackOverviewPage.a11y.test.tsx
6. apps/web/src/i18n/locales/de.json
7. apps/web/src/i18n/locales/en.json
8. changelog.d/t-149e2237-feedback-hub-cases.added.md

## Schritte
1. Seite: `?tab=` (cases|signals|curation), Rolle aus `useCurrentWorkspaceRole`.
   viewer: nur „Meine Fälle“ ohne Tab-Leiste. Unbekannt/nicht erlaubt → replace auf cases
   (waehrend die Rolle laedt, bleibt ein Editor-Tab stehen – wie MemoryPage).
   Kopf: „Problem melden“ (outline, unveraendert) + `ReportCaseDialog variant="brand"` ohne Agent.
2. CaseList: ListFilterBar mit statusOptions (Alle/Offen/Eingeordnet/Umgesetzt/Verworfen,
   Zahlen aus /cases/counts, ohne Zahl bei gesetztem target), Facetten Agent (alle) +
   „Zugeordnet zu“ (nur editor), keine Suche. URL `status` (fehlt = open), `agent`, `target`, replace.
   Offen → `status=open&status=reopened`. Cursor-Paginierung, „Weitere laden“.
   Zeile: EntityCard, Agent als Titel, Status (Punkt+Wort), Erwartet, Lage (ab md), Meta.
   Zustaende: 3 Skeletons, Leer (editor offen / gefiltert / viewer), Fehler + Erneut versuchen.
3. Tests: viewer/editor, Tab-Fallback, Offen sendet beide Status, Paginierung, axe je Tab.
4. Checks: tsc -b, vitest, lint, i18n; Fotos 1280/390 hell/dunkel + measure.json; e2e-mobile.

## Bekannte Grenzen
- Nach „Fall melden“ laedt die Liste nicht von selbst neu: `ReportCaseDialog` hat keinen
  Erfolgs-Callback, und ReportCaseForm.tsx liegt ausserhalb des Budgets (D6c fasst sie an).
- Repo hat keine Radix-Tabs, sondern `components/ui/tabs` (ARIA-Tabs-Pattern) – wird genutzt.
- Die Route `/w/:ws/feedback/cases/:id` kommt erst mit D6c; bis dahin fuehrt der Zeilen-Link auf 404.
- e2e-mobile lokal nicht lauffaehig (kein Docker auf dem Host); Nachweis ueber CI-Job `e2e-mobile`.

## Stand
- [x] 1–3 umgesetzt. tsc -b gruen, lint 0 errors, i18n:check gruen, test:coverage 250/2030 gruen
  (Node 22 via mise; Node 26 bricht lokal an Web Storage, CONTRIBUTING §Node 22), build gruen.
- [x] Fotos: 26 PNG + measure.json, kein Ueberlauf.
