# E5a: Rückmeldung — Status in_progress/verified und Begriffe in Fall-Liste und Fall-Detail

Karte t_df5e60f4 · Basis origin/main 06ddb3fb · Specs: E-Delta §6.1/§8/§9.3 + Neuschnitt
(`phase-e-web-neuschnitt-2026-10.md`, geht vor) §1, §7.1 Zeile E5a.

## Dateien (8, Grenze 8)
1. `apps/web/src/features/feedback/components/CaseList.tsx`
2. `apps/web/src/features/feedback/components/CaseList.test.tsx`
3. `apps/web/src/features/feedback/pages/CaseDetailPage.tsx`
4. `apps/web/src/features/feedback/pages/CaseDetailPage.test.tsx`
5. `apps/web/src/i18n/locales/de.json`
6. `apps/web/src/i18n/locales/en.json` (nur neue Keys, N3 a)
7. `changelog.d/case-status-in-progress-verified.added.md`
8. `apps/web/src/features/feedback/pages/FeedbackOverviewPage.test.tsx` (nachgezogen:
   Erwartungen an die umbenannten Leerzustände der Liste)

## Schritte
1. CaseList: Chips Alle · Offen · Eingeordnet · In Arbeit · Geändert · Hat gewirkt · Verworfen,
   Zähler aus `countCases`. Punktform als exportierte Komponente `CaseStatusDot`
   (filled / hollow = addressed / ring = in_progress, `data-shape`, `aria-hidden`).
2. CaseDetailPage: Token + `CaseStatusDot`, Erklärsatz unter dem Kopf für alle Rollen
   (`cases.status.explain.*`, ohne Link), `KNOWN_EVENTS` + `in_progress`, `verified`,
   `reopenedByFollowUp` (reopened + measure_id + System), `addressedOnActivation`
   (addressed + System, mit Element und Version).
3. Locales: neue Keys (DE/EN), DE-Werte der in Liste/Detail gerenderten `feedback.cases.*`
   nach A4a (Fall → Rückmeldung, Umgesetzt → Geändert, Bestätigt → Hat gewirkt).
   `report.*` und `list.description*` bleiben (T2, Hub/Melden).
4. Tests: Chips/Zähler editor+viewer, Punktformen per `data-shape`/Klasse, vier Verlaufstexte,
   kein Knopf/Menüpunkt für in_progress/verified, axe je Zustand eigenes `it()` (15 s).
5. DoD aus CONTRIBUTING, Fotos 1280/390 hell/dunkel + measure.json, PR.

## Entscheidungen
- Neue Texte folgen den A4a-Begriffen (Neuschnitt §1 geht vor E-Delta §9.3):
  Maßnahme → Änderung, Gespräch → Review, Nachschau → Nachkontrolle; EN nach §1 (change, review,
  follow-up check). Keine Keys `cases.chip.*` — die Chips nutzen wie auf main `cases.status.*`.
- Kein Link „Zur Maßnahme“ (E5h).
