# E5h — Fall-Detail: Verknüpft (Review, Änderung), Fällig-Pill, Verlauf-Links, → Weiterentwicklung

Karte t_28a20afa · Basis origin/main 47f270c7 · Spec phase-e-web-neuschnitt-2026-10.md §1, §6, §7.1 (geht vor),
E5-Delta §6.1 (letzter Absatz), §6.2, §8, §9.3. `api/client.ts` bleibt unverändert: `listSessions` kennt `case_id` seit E5b.

## Completion-Condition
- editor: genau ein `listSessions({case_id}, {limit: 10})`, danach je Review ein `getSession` (höchstens 10, parallel; Muster E5g §3.4).
  Es zählen nur Reviews, deren `case_ids` den Fall enthalten, und Änderungen mit `session_id` des Reviews und dem Fall in `case_ids`
  (nichts aus URL/Eingabe, nur Serverdaten).
- „Verknüpft“: je Änderung zwei Zeilen „Review vom {{date}}“ → `/agents/:agentId/reviews/:sid` und
  „Änderung: {{element}} · {{state}}“ → `…?change=:mid`, dazu `ChangeDueMark` (Fällig-Pill bzw. „Nachkontrolle am“).
  Zustand = `measure.state` vom Server, nie aus Events nachgerechnet.
- Kopf: Pill „Nachkontrolle fällig“, wenn eine Änderung des Falls fällig ist (nur editor); Link „Zu {{agent}} → Weiterentwicklung“
  (`?tab=evolution`) für editor und viewer.
- Verlauf: Ereignis mit `measure_id` bekommt für editor „Zur Änderung“, nur wenn die Änderung in den geladenen Reviews steckt.
- viewer: kein `listSessions`/`getSession`, keine Links außer → Weiterentwicklung, keine Pill.

## Dateien (5)
features/feedback/pages/CaseDetailPage.tsx · CaseDetailPage.test.tsx · de.json · en.json · changelog.d/case-detail-linked-changes.added.md

## Verifikation
`npm run lint`, `npx tsc -b`, `npm run test:coverage`, `npm run build`, e2e-mobile; Fotos 1280/390 hell/dunkel editor+viewer + measure.json.
Mutationen: viewer-Gate, Request-Grenze (limit, kein Request je Element), fremde IDs (Review ohne Fall, Änderung fremder Session),
Server-Zustand statt Events, Verlauf ohne auflösbare Session.
