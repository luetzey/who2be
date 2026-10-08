# D6c – Fall-Detail lesend, Löschen, Route (Karte t_b7f9df4f)

Basis: origin/main 29d373a5 (D6b gemergt). Spec: Delta Phase D §0, S8 (ohne
„Nächster Schritt“, Triage-Dialoge, „Verknüpft“), Barrierefreiheit.
PM-Entscheidung Schnitt A: die mobile Melden-Seite (`/feedback/cases/new`,
FeedbackComposePages, ReportCaseForm) geht nach D6c′ (t_b3b7835c).
PM-Abweichung von S8: „Fall löschen…“ ab editor (Q6, `DELETE /cases/{id}`).

## Dateien (Budget 8)
1. apps/web/src/features/feedback/pages/CaseDetailPage.tsx (neu)
2. apps/web/src/features/feedback/pages/CaseDetailPage.test.tsx (neu)
3. apps/web/src/app/routes.tsx (`/feedback/cases/:caseId`)
4. apps/web/src/features/feedback/components/CaseList.tsx (Filter am Link, Nits c/d)
5. apps/web/src/features/feedback/components/CaseList.test.tsx (Tests Nits c/d, Link)
6. apps/web/src/i18n/locales/de.json
7. apps/web/src/i18n/locales/en.json
8. changelog.d/t-b7f9df4f-case-detail.added.md

## Schritte
1. CaseDetailPage: `GET /cases/{id}` + `GET /agents`; Kopf „Fall · {{agent}}“,
   Status (Punkt + Wort), „gemeldet am …“, Overflow „ID kopieren“ (+ „Fall
   löschen…“ für editor). SBI 2×2 ab `md`, leere Blöcke weg, Hinweis
   „Inhalt unveränderlich“, Schilderung (neueste) mit Badge, Zuordnung nur
   editor (lesend), Verlauf neueste zuerst mit Fallback `unknown`, unter `md`
   eingeklappt. 404 (auch fremder Fall für viewer) → eigene Darstellung.
   Elementnamen über die Element-GETs, Version bei `addressed` über die
   Versionslisten der zugeordneten Elemente; ohne Treffer nur „Umgesetzt“.
2. Löschen: destruktiver Dialog; Text nach Code (`case_repository.delete_case`):
   Fall samt Verlauf, Zuordnung und Schilderungen weg, ein inhaltsfreier
   Protokolleintrag bleibt; ein Lernvorschlag, aus dem der Fall wurde, wird
   mitgelöscht. Danach zurück zur Liste (mit Filter) + Toast.
3. CaseList: Filter-Query (`status`, `agent`, `target`) am Zeilen-Link; die
   Detailseite baut daraus `/feedback?tab=cases&…`. Nit (c) eigener
   viewer-Leertext, Nit (d) Liste lädt erst bei bekannter Rolle.
4. Tests: viewer eigen/fremd (404), Verlauf inkl. Fallback, Löschen (editor
   sichtbar, viewer nicht), Rückweg mit Filter, axe.
5. Checks: tsc -b, vitest (coverage), lint, i18n, build; Fotos 1280/390
   hell/dunkel + measure.json.

## Bekannte Grenzen
- Nit (b) Neuladen nach „Fall melden“: braucht einen Erfolgs-Callback in
  ReportCaseForm.tsx (nicht im Paket) → offen, D6c′ fasst die Datei an.
- Nit (d) im Seitenkopf (`FeedbackOverviewPage`: Beschreibung/Überschrift der
  viewer-Variante während die Rolle lädt) liegt außerhalb des Budgets; die
  Liste selbst lädt und rendert erst bei bekannter Rolle.

## Stand
- [ ] 1–5
