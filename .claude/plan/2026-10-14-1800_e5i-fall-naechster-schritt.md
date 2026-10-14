# E5i: Fall-Detail „Nächster Schritt“ in Phase E (t_846efca2)

Basis: origin/main 03b91b6c (E5h #972). Spec: E5-Delta §6.3 + Fußnote ¹, §8, §9.3;
Neuschnitt §6 (Begriffe A4a, Routen N4 a). Budget 8 Dateien (ohne diese Plan-Datei).

## Outcome
Der nächste Schritt im Fall-Detail folgt der Tabelle §6.3. Hauptaktionen sind
„Review vorbereiten“, „Zur Änderung“ und „Zur Nachkontrolle“ (Links, keine
Übergänge). „Als geändert markieren…“ steht nur noch im Menü, und der Dialog
trägt den Satz `cases.address.noFollowUp`.

## Tabelle (umgesetzt in `nextStep`)
| Zustand | Hauptaktion | Menü |
|---|---|---|
| open/reopened | unverändert | unverändert |
| triaged ohne Prüffall | createTestCase | prepareSession, address¹, changeAssignment, dismiss |
| triaged mit Prüffall | prepareSession (brand, Link) | address¹, changeAssignment, dismiss |
| in_progress | toMeasure (default, Link), nur mit bekannter Änderung | address¹, dismiss |
| addressed + offene Änderung | toFollowUp (default, Link) | reopen |
| addressed ohne offene Änderung | toVersion (unverändert) | reopen |
| verified | toFollowUp, nur mit bekannter Änderung | – |
| dismissed | – | – |

¹ nur mit versioniertem Baustein, sonst Hinweis (D6d-Bestand). Modellgrenze:
Verwerfen bleibt Hauptaktion in open/reopened/triaged.

## Entscheidungen (mit Beleg)
- Route „Review vorbereiten“: `/agents/:agentId/reviews/prepare?cases=<id>`
  (Weiche N4 a ersetzt QE12; Karte nennt noch `/feedback/sessions/prepare`).
- „Zur Nachkontrolle“ = Deep-Link `?change=<measureId>` ins Änderung-Sheet
  (Neuschnitt §2), derselbe wie „Zur Änderung“.
- Welche Änderung: die des jüngsten Fall-Ereignisses mit `measure_id`, die in
  den geladenen Reviews steckt (E5h-Daten, kein weiterer Request); sonst die
  erste offene, sonst die erste. `open` = Server-Feld `measure.state` nicht
  abgeschlossen (`isClosedState`), nicht aus `events` abgeleitet.
- Fallstatus aus `case.status` vom Server, nie aus dem Verlauf.
- Fehler beim Schreiben: 409/422 → Text „passt nicht zum aktuellen Stand“ und
  Neuladen (Fall und Änderungen). Doppel-Submit per Ref-Sperre.
- Leiste erscheint erst, wenn Prüffälle UND Änderungen geladen sind (kein
  Springen der Hauptaktion).

## Schritte
1. `lib/caseNextStep.ts` + Test (jede Zeile, address nie Hauptaktion).
2. `CaseActions.tsx`: Links, Satz im Dialog, 409/422, Doppel-Submit-Sperre.
3. `CaseDetailPage.tsx`: Änderungs-Bezug ableiten, durchreichen, Reload.
4. `CaseDetailPage.test.tsx`: Rendering je Zeile, Server≠lokal, viewer, axe je Zustand, M11.
5. de/en, Fragment. DoD: tsc -b, vitest, lint, e2e-mobile; Fotos.

## Stand 2026-10-14
Alle Schritte erledigt. DoD lokal (Node 22.23.3): lint 0 Fehler (90 Warnungen
wie auf main), tsc -b gruen, vitest --coverage 266 Dateien / 2491 Tests gruen,
Skip-Budget 0, build gruen, license:check gruen. e2e-mobile braucht den
Compose-Stack; keine E2E-Spec beruehrt die Fallseite, Nachweis ueber CI.
M11 (detail.session.id === row.id) bewusst nicht mitgenommen (optional).
