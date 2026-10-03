# Web: MemoryDetailSheet auf Einzelabruf `GET /memories/{id}` (t_b6bfcb87)

Folge aus t_ef8822fa (PR #809). Heute loest `DetailBody` `?entry=<id>` ueber
bis zu 10 Seiten `listMemories` auf; jeder Fehler (auch Netzfehler) wird zu
„nicht gefunden“.

## Completion-Condition

- `api.getMemory(id)` → `GET /v1/workspaces/{ws}/memories/{id}`, im
  Contract-Test aufgerufen (Pfad im OpenAPI-Golden).
- Sheet nutzt ausschliesslich den Einzelabruf (kein `listMemories`, keine
  Rollen-Fallunterscheidung `canManageAgents ? {} : { scope: 'user' }`).
- 404 / `memory_not_found` → bisheriger Zustand `detail.notVisible`.
- Andere Fehler → `ErrorAlert` (bestehende Komponente) + „Erneut versuchen“;
  Retry ruft erneut ab.
- `initial` aus der Liste wird ohne Abruf gezeigt.
- Tests: Erfolg, 404, Netzfehler + Retry erfolgreich. Rot-Probe: Netzfehler
  als 404 behandelt → Test rot.
- i18n de/en (`detail.loadError`), `i18n:check` gruen.
- Web-DoD unter Node 22: lint, `tsc -b`, `test:coverage`, build, `license:check`.

## Entscheidungen

1. `visibleToMe` bleibt als Abwehr auch auf dem Abrufergebnis (wie bei
   `initial`, 3.1.1) — kostet nichts, keine zweite Regel.
2. Fehlermeldung wie `MemoryHistory`: `ErrorAlert title=… message=cause.message`
   plus Outline-Knopf `common:actions.retry` (gleiches Muster, kein Neubau).
3. `DEEP_LINK_PAGES` entfaellt (keine weiteren Nutzer im Repo).
4. `types.ts` bleibt unveraendert (`MemoryRead` existiert).

## Dateien (8, ohne diese Plan-Datei)

1. apps/web/src/api/client.ts
2. apps/web/src/api/client.contract.test.ts
3. apps/web/src/components/memory/MemoryDetailSheet.tsx
4. apps/web/src/components/memory/MemoryDetailSheet.test.tsx
5. apps/web/src/components/memory/AgentMemoryCard.test.tsx — nur der
   Fetch-Stub: der Deep-Link-Test der Agent-Seite stubbte den alten
   Listenweg (Komponente selbst unberuehrt, kein Out-of-Scope-Eingriff)
6. apps/web/src/i18n/locales/de.json
7. apps/web/src/i18n/locales/en.json
8. changelog.d/t-b6bfcb87-memory-detail-einzelabruf.changed.md

## Schritte

- [x] client.ts + Contract-Test
- [x] Sheet umstellen
- [x] i18n
- [x] Tests + Rot-Probe (Netzfehler als 404 behandelt -> 2 Tests rot:
      Netzfehler+Retry, Serverfehler 500; zurueckgesetzt)
- [x] Changelog-Fragment
- [x] Web-DoD (Node 22): lint 0 Fehler (90 Warnungen = main-Baseline), tsc -b, i18n:check, test:coverage 1825/1825, build, license:check gruen
- [x] Push, PR, CI (PR #811, 17/17 gruen auf ec6c9a54)
- [x] Review Runde 1: getMemory kodiert die ID (`encodeURIComponent`, CSPT aus `?entry=`),
      Test mit `entry=..%2F..%2Fx` (Rot-Probe ohne Kodierung -> rot); Screenshots
      1280/390 hell/dunkel fuer Fehler- und Nicht-gefunden-Zustand mit Messwert im Sheet
