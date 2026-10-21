# Navigation W1-c: Dashboard ohne Aufmerksamkeits-Band, Zeile „Zu erledigen“

Kanban-Karte t_40e671d2 · Spec `navigation-transparenz-design-2026-10.md` §2.5 · ersetzt E5j.

## Ziel (fertig heißt)

Das Band „Braucht jetzt deine Aufmerksamkeit“ (`dashboard.attention.*`, fünf
`AttentionBanner` plus „Alles erledigt“) ist vom Dashboard verschwunden. An
seiner Stelle steht eine Zeile `InboxSummary`, die aus `useInboxCounts` zählt,
also aus derselben Quelle wie Glocke und Seite „Zu erledigen“.

## Schritte

1. [x] `components/data/InboxSummary.tsx` (neu): Card-Rand, Icon-Kachel `Bell`,
   Titel „n Aufgaben warten auf dich“, Arten > 0 (höchstens drei, Rest
   „+ n weitere“), `outline` „Alle ansehen →“ auf `/inbox`, unter `md` volle
   Breite und 44 px. Bei 0 `CircleCheck` „Nichts zu erledigen.“ ohne Knopf.
   Beim Laden ein Skeleton, bei einem Fehler keine Zeile.
2. [x] `DashboardPage.tsx`: Band raus, Zeile rein. `useEditorCount`,
   `useApprovalCount`, `listPatterns`, `countCases` und `useReviewTargets`
   fallen weg; die Seite fragt nur noch `/inbox/counts` an.
3. [x] `hooks/useReviewTargets.ts` entfernt, weil es keinen Verwender mehr gibt.
4. [x] i18n de/en: `dashboard.attention.*` entfernt, `dashboard.inbox.*` neu.
   Es gibt keine neuen Waisen, die orphan-baseline bleibt unverändert.
5. [x] Tests: `DashboardPage.test.tsx` (Band-Blöcke ersetzt durch W1-c-Block),
   `DashboardPage.a11y.test.tsx`.
6. [x] Changelog-Fragment.
7. [ ] Fotos 1280/390 hell/dunkel + measure.json, e2e-mobile.

## Arten der Zeile (Regel aus Spec §2.2)

Die Arten erscheinen in der Reihenfolge Nachkontrollen fällig, Gedächtnis,
Versionen und Rückmeldungen. Versionen (inkl. System-Prompts) zeigt die Zeile
nur für admin, so wie sie auch in `total` eingehen. Muster stehen nie in der
Zeile. Der Titel nennt `total` vom Server, die Arten werden aus denselben Feldern
gerechnet, deshalb stimmen Titel und Summe der Arten überein.

## Abgleich: was das alte Band zeigte und wo es jetzt steht

| Altes Band | Neu |
|---|---|
| n Versionen liegen zur Review + Direktlinks/Listenlinks | admin: Art „Versionen zur Freigabe“ in Glocke/Zeile, Zeilen mit Direktlink auf „Zu erledigen“. editor: „Zum Anschauen“ auf „Zu erledigen“ mit Link auf die gefilterte Liste. viewer: entfällt (darf nicht freigeben, Spec §2.2) |
| n System-Prompts liegen zur Review | in „Versionen zur Freigabe“ mitgezählt (`system_prompts_review`), Zeile auf „Zu erledigen“ |
| n Einträge zur Freigabe (Gedächtnis) | Art „Gedächtnis zur Freigabe“, alle Rollen (viewer nur eigenes Nutzergedächtnis) |
| n Muster | „Zum Anschauen“ auf „Zu erledigen“ (zählt nicht in die Glocke, ADR 3.7) |
| n offene Fälle | Art „Rückmeldungen, nicht eingeordnet“ |
| Alles erledigt | „Nichts zu erledigen.“ in der Zeile bzw. EmptyState auf „Zu erledigen“ |
