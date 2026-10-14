# E5c: Review-Ergebnis-Seite, Korrektur-Kopierblock, Route (Karte t_7e629103)

Grundlage: Neuschnitt `phase-e-web-neuschnitt-2026-10.md` §1, §2, §4, §7.1 (Zeile E5c),
für die Inhalte E5-Delta §0.3, §0.5, §2, §8, §9.1. Bei Widerspruch gilt der Neuschnitt.

## Completion-Condition
- Route `/w/:ws/agents/:agentId/reviews/:sessionId` rendert `ReviewDetailPage`. Passt die agentId nicht: `replace`.
- AK1: Die Korrektur ist in beiden Richtungen getestet (Meta-Link „Korrigiert …“, Banner „Ersetzt durch …“). Der Kopierblock entfällt bei einem ersetzten Ergebnis.
- AK2: Teilnehmende inklusive der Fallbacks Ehemaliges Mitglied, Gelöschter Agent und Builder sind getestet.
- AK3: Ein viewer bekommt die 404-Darstellung. Für ihn gibt es keinen Abruf, also kann kein Inhalt aufblitzen.
- AK4: Der Kopiertext enthält Session-ID, Agent-Name und Agent-ID, aber keinen Freitext.
- AK5: h1, darunter je Abschnitt ein h2; axe bekommt je Zustand ein eigenes `it()`.
- Prüfkommandos: `npx tsc -b`, `npx vitest run`, `npx eslint`, `e2e-mobile` (CI), Fotos plus `measure.json`.

## Entscheidungen (aus dem Repo belegt)
- `superseded_by_id` gibt es nur an `SessionListItem`, nicht an `SessionDetail` (openapi.json).
  Die Seite liest deshalb `listSessions({agent_id})`, neueste zuerst, und blättert, bis die eigene Zeile kommt (höchstens 5 Seiten zu je 200).
  Die Route bleibt unverändert (PM-7). Der Kopierblock erscheint erst, wenn das Ergebnis vorliegt.
- `GET /members` darf jedes Mitglied lesen (routers/members.py). Die Namen kommen aus `email`.
- Pill an der einzelnen Änderung: `followUpStatus` (PM-Leitplanke 2026-10-14). Das Zustandswort kommt vom Server (`measure.state`).
- Sheet-Parameter `?change=<id>` (Neuschnitt §2). Das Sheet selbst baut E5d.
- i18n-Namespace `sessions` (E5-Delta §9). DE-Werte nach den A4a-Begriffen, EN nach Neuschnitt §1.

## Dateien (7)
ReviewDetailPage.tsx, ReviewDetailPage.test.tsx, BuilderPromptCopy.tsx, routes.tsx, de.json, en.json, Fragment.

## Stand (2026-10-14)
- Erledigt. Nachgezogen: `CaseStatusDot` liegt jetzt in `components/cases/`, weil ESLint keine Importe zwischen Features erlaubt. CaseList und CaseDetailPage importieren ihn von dort.
- Prüfungen mit Node 22 (mise): `tsc -b` ok, `npm run lint` 0 Fehler (die 90 Warnungen sind Altbestand, in den neuen Dateien keine), `i18n:check` ok, `test:coverage` 2297/2297, `build` ok, `license:check` ok.
- Fotos: 3 Ansichten × 1280/390 × hell/dunkel, measure.json überall scrollWidth == clientWidth.
- Nach der Fotoprüfung angepasst: Das Banner „Ersetzt durch …“ legt den Knopf auf 390 px in volle Breite unter den Text.
