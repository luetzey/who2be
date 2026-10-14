# E5b: API-Spiegel Review + Nachkontroll-Logik (Karte t_6ac31fe3)

Grundlage: Neuschnitt-Spec `phase-e-web-neuschnitt-2026-10.md` §7.1 Zeile E5b
(ersetzt den Karteninhalt laut PM 2026-10-10; Weiche N1 a: kein Hub-Tab).
Zustände nach §1 (ersetzt E5-Delta §0.4, Spalte DE), Fällig-Regel E5-Delta §0.4.

## Outcome
Web kennt die Typen und Client-Methoden der Protokoll-/Maßnahmen-Routen auf
main (E2b-3/E2b-4) und eine reine Funktion für Zustand, Nachkontroll-Datum,
fällig (zwei Varianten) und „seit n Tagen“. Ohne UI.

## Dateien (7 von max. 8)
1. `apps/web/src/api/types.ts` — SessionRead, SessionListItem, SessionDetail,
   MeasureRead, MeasureEvent, MeasureVerdict, MeasureState, SessionFilters,
   SessionPage, FollowUpReport (+ VersionReport, RunRate). Quelle:
   `packages/models/src/who2be_models/session.py`, `services/measure_service.py`.
2. `apps/web/src/api/client.ts` — listSessions (agent_id, case_id, due, cursor,
   limit; `X-Next-Cursor`), getSession, getFollowUp.
3. `apps/web/src/features/evolution/lib/followUp.ts` (neu).
4. `apps/web/src/features/evolution/lib/followUp.test.ts` (neu).
5. `apps/web/src/api/client.contract.test.ts` — drei neue Aufrufe.
6. `apps/web/src/api/client.test.ts` — Query-Parameter und Cursor von listSessions.
7. `changelog.d/t-6ac31fe3-e5b-api-spiegel-nachkontrolle.added.md`.

Abweichung: Datei 6 steht nicht in der Spec-Zeile; sie belegt die
Query-/Cursor-Abbildung (Budget 8 bleibt eingehalten, 7 Dateien).

## Verifikation
`npx tsc -b`, `npx vitest run src/features/evolution src/api`, `npm run lint`,
volle Vitest-Suite. Fotos: entfallen, keine sichtbare UI-Änderung.

## Review-Runde 1 (B1)
Sommerzeit-Test: eigener Block mit fest gesetztem `process.env.TZ =
'Europe/Berlin'` plus Wächter-Test (Offset Winter −60, Sommer −120), damit er
auch in einer CI unter UTC eine Umstellung sieht. Frühjahr 29.03. und Herbst
25.10. Mutation `Math.floor((to - from)/86_400_000)` muss unter TZ=UTC und
TZ=Europe/Berlin rot sein. Dazu ein Satz in `followUp.ts`, dass der Server
mit dem UTC-Kalendertag rechnet.
