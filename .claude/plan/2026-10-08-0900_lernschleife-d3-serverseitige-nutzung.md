# D3 — Serverseitige Nutzungsaufzeichnung (`usage_event.source`, Migration 0101) (Kanban t_f7f33984)

Basis: origin/main 5e28bb2e (D2c gemergt). Norm: ADR-0053 Abschnitt 3.4,
Anhang A.2 (Zeile D3), Owner-Weichen N1 = a, N2 = a.

## Completion-Condition

1. Migration `0101_usage_event_source.sql`: Spalte `usage_event.source text NOT NULL
   DEFAULT 'agent_report'` mit DB-CHECK `agent_report · server`.
2. Schreibstellen (best-effort nach der Fachtransaktion, nur agent-gebundene
   Aufrufer, `outcome=NULL`, `version` = ausgelieferte Version):
   `PersonaService.render`, `PlaybookService.render`, Resource-Abruf
   (`ResourceService.retrieve`, aufgerufen von `GET /resources/{id}`).
3. Auswertung in `feedback_repository.py`: `summarize` und `overview` zaehlen
   Nutzungen nur aus `source='server'`, Ergebnisse (`by_outcome`) nur aus
   `source='agent_report'`; `unused` prueft „genutzt“ ebenfalls nur ueber
   `source='server'` (W2).
4. Tests mit echter DB: Agent-Abruf → genau eine `server`-Zeile je Abruf (alle
   drei Stellen); Mensch → keine; Schreibfehler → Abruf 200, keine Zeile;
   `summarize`/`overview` mit Fixture aus beiden Quellen. Mutationsprobe:
   `source`-Filter in `summarize` entfernen → Test rot.
5. Python-DoD mit `WHO2BE_REQUIRE_DB=1`, 0 skipped; CI `all-green`.

## Weichen (aus dem Repo entschieden)

- **W1 Resource-Abruf = `GET /resources/{id}`, nicht `ResourceService.get`.**
  `get` wird intern von `duplicate`, `list_blocks`, `_check_update_tags` und
  `WaPromoteService._update_target` mitbenutzt; dort aufzuzeichnen ergaebe
  Nutzungen fuer Schreibvorgaenge. Neue Methode `retrieve` = `get` + Aufzeichnung,
  nur der Router ruft sie. Das MCP-Tool `fetch_resource` geht ueber genau diesen
  Endpunkt (`apps/mcp/src/who2be_mcp/client.py`).
- **W2 `unused` zaehlt wie `usage_count` nur `source='server'`.** Die Karte
  nennt den ADR-Wortlaut verbindlich und listet `unused` ausdruecklich unter
  „trennen nach `source`“; damit bleibt `unused` konsistent mit
  `overview.usage_count`. Folge: ein Element, das bisher nur per
  `record_usage` gemeldet wurde, gilt nach dem Deploy wieder als ungenutzt, bis
  der Server eine Auslieferung aufzeichnet (Changelog nennt das).
- **W3 Helfer im Repository-Modul.** `record_server_usage(pool, workspace_id,
  agent_id, actor_id, …)` in `feedback_repository.py`: No-op ohne `agent_id`,
  faengt jede Exception, zaehlt `failed_usage_writes()` hoch (Muster
  `access_log.log_access`). Spart eine neue Datei (Budget).

## Dateien (Budget 8)

1. `apps/api/src/who2be_api/migrations/0101_usage_event_source.sql` (neu)
2. `apps/api/src/who2be_api/repositories/feedback_repository.py`
3. `apps/api/src/who2be_api/services/persona_service.py`
4. `apps/api/src/who2be_api/services/playbook_service.py`
5. `apps/api/src/who2be_api/services/resource_service.py`
6. `apps/api/src/who2be_api/routers/resources.py` (W1: `retrieve`)
7. `apps/api/tests/test_feedback.py` (Bestandstest an neue Zaehlung + neue Tests)
8. `changelog.d/t-f7f33984-usage-event-source.changed.md`
9. `apps/api/tests/test_render_scope_propagation.py` — **ueber Budget (+1)**,
   erst beim vollen Testlauf sichtbar: die Attrappen von Persona/Playbook
   tragen kein `id`/`current_version`, die `render` jetzt fuer die
   Aufzeichnung liest. Zwei Felder je Attrappe, kein Verhaltenswechsel.

Nicht im Diff: `docs/reference/openapi.json` (Antwortformen unveraendert).

## Verifikation

- Mutationsproben gegen `test_feedback.py` (je einzeln, danach zurueckgesetzt):
  source-Filter `summarize.usage_count` → 3 rot; FILTER in `overview` → 3 rot;
  source-Filter in `unused` → 1 rot; best-effort-Fang (`except KeyError`) →
  1 rot; Mensch-Sperre → 2 rot; Router zurueck auf `get` → 2 rot.
  Source-Filter auf `by_outcome` → gruen: aequivalenter Mutant, Server-Zeilen
  tragen immer `outcome = NULL`, `outcome IS NOT NULL` schliesst sie bereits
  aus. Der Filter bleibt als Klarstellung der Regel im SQL.
- `test_org_transfer.py` schlaegt gegen die geteilte Dev-DB fehl (dort ist eine
  Migration eines fremden Zweigs eingetragen); gegen eine frische DB gruen.

## Schritte

1. Migration + Repository (Insert mit `source`, Aggregation getrennt, Helfer).
2. Schreibstellen in den drei Services + Router.
3. Tests (rot/gruen), Mutationsprobe.
4. DoD, Changelog, Push, PR.
