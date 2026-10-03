# Lernschleife C3c-2b — Stapel und Mitglieder-Purge, Schicht 2 (Router)

Karte: t_f485a023 (PM-Schnitt vom 2026-10-02: C3c-1a → 1b → 2a → 2b → 3).
Grundlage: C3c-2a (#795, main 453f49e3) mit `MemoryService.batch` und
`MemoryService.purge_user_memories` sowie den Modellen `MemoryBatchRequest`,
`MemoryBatchResult`, `MemoryPurgeResult`. Norm: ADR-0053 6.4.1.

## Outcome

`POST /v1/workspaces/{ws}/memories/batch` und
`DELETE /v1/workspaces/{ws}/members/{user_id}/memories` sind erreichbar, reichen
an den Service durch und tun selbst nichts weiter (ausser den Router-Gates des
Members-Routers).

## Dateien (7 + dieser Plan)

1. `apps/api/src/who2be_api/routers/memory.py`: `POST /memories/batch`
   (`write_limit`), Antwort `MemoryBatchResult`.
2. `apps/api/src/who2be_api/routers/members.py`: `DELETE /{user_id}/memories`
   mit `require_role(admin)` + `deny_agent_bound_workspace_admin` am Router
   (wie die Nachbarrouten), `write_limit`, Antwort `MemoryPurgeResult`
   (`{deleted: n}`). Der Memory-Service kommt ueber `get_memory_service` aus
   `routers/memory.py` (Muster `wa_tables.py` → `get_wa_artifact_service`).
3. `apps/api/tests/test_memory_batch_purge_api.py`: Router-Tests ueber HTTP.
4. `apps/api/tests/test_tenant_isolation_api.py`: zwei Proben.
5. `apps/api/tests/contract/openapi_surface.json`: Golden.
6. `apps/api/tests/contract/gate_inventory.json`: neue `ungated`-Zeile fuer
   die POST-Route mit Begruendung (DELETE erfasst das Inventar nicht).
7. `docs/reference/openapi.json`: Export.
8. `changelog.d/t-f485a023-lernschleife-c3c-2b-batch-purge-router.added.md`.

Das sind 8 Dateien laut Kartenumfang plus der vorgeschriebene Plan.

## Vorentschiedene Weichen (Beleg im Repo)

- Statuscode Stapel: 200 mit `{results}` — auch bei Teilerfolg; Fehler je
  Eintrag stehen im Ergebnis (ADR 6.4.1 „Antwort `{results:[...]}`“).
- Statuscode Purge: 200 mit `{deleted: n}` statt 204, weil die Karte die
  Anzahl in der Antwort verlangt (ADR 6.4.1 W5 = a „Anzahl“).
- Purge prueft die Mitgliedschaft der Person NICHT: `subject_user_id` hat
  keinen FK (0091) und das Nutzergedaechtnis ueberlebt das Entfernen eines
  Mitglieds (`workspace_member_repository.remove` loescht es nicht). Ein Admin
  muss es also auch nach dem Austritt loeschen koennen; eine unbekannte Person
  ergibt `{deleted: 0}`. Kein Orakel: die Antwort ist fuer fremde und
  unbekannte IDs gleich, und Rollen/Workspace-Scope schuetzen den Pfad.
- Doppelte Rollenpruefung (Router + Service) beim Purge ist gewollt: Router
  wie die Nachbarrouten in `members.py`, Service bleibt Single Source der
  Fachregel (auch ohne Router aufrufbar).
- Rate-Limit: `write_limit` an beiden mutierenden Routen (F-Phase2-01-Muster).

## Mandantentrennung

- `POST /memories/batch`: Body `{action: "reject", ids: ["<<memory_id>>"]}`.
  V1 (fremder Workspace) → 403/404. V2 (eigener Workspace, B-ID): Antwort 200
  mit `memory_not_found` je Eintrag — deshalb `filters=True` (die Referenz
  waehlt aus, statt die Route zu adressieren); Leck-Check und Orakel-Vergleich
  (Geist-ID liefert dieselbe Antwort, B-ID wird nur zitiert) bleiben. Der
  Fingerabdruck von B belegt, dass nichts geschrieben wurde.
- `DELETE /members/{user_id}/memories`: V1 und V2 mit `user_id` von B; V2 im
  eigenen Workspace ergibt `{deleted: 0}` → ebenfalls `filters=True`, der
  Fingerabdruck belegt, dass bei B nichts geloescht wurde.

## Verifikation

- `uv run ruff check . && uv run ruff format --check . && uv run mypy .`
- Router-, Isolations-, Gate-Inventar- und OpenAPI-Vertragstest gezielt
- volle DoD laut CONTRIBUTING.md auf frischer DB
- Rot-Proben: Router reicht `ids` nicht durch / ignoriert `filter`; Router-Gate
  `require_role(admin)` beim Purge entfernt (Service faengt es — belegt die
  Doppelung); Workspace-Filter im Purge entfernt (Isolationstest)

## Ergebnis Rot-Proben (2026-10-03, je danach zurueckgedreht)

| Mutation | rot durch |
|---|---|
| M1 Purge-DELETE ohne `workspace_id`-Filter | Isolationslauf: Fingerabdruck von B veraendert |
| M2 `get_batch_targets` ohne `workspace_id`-Filter | `test_eintrag_aus_fremdem_workspace_ist_nicht_gefunden` (`agent_not_found` statt `memory_not_found` — ein Orakel, das der Statuscode-Vergleich im Isolationslauf nicht sieht; deshalb dieser eigene Test) |
| M3 Router verwirft `note` | `test_stapel_teilerfolg_mit_ergebnis_je_eintrag` |
| M4 Router-Gate Purge `admin` → `editor` | `test_purge_nur_admin_nur_anzahl` (Agent-Token liefe in das zweite Gate) |

Abweichung vom Plan: Agent-gebundene Tokens scheitern beim Purge schon an der
Rolle (`AGENT_BOUND_MAX_ROLE = editor`, `insufficient_role`), nicht an
`deny_agent_bound_workspace_admin`; das zweite Gate bleibt wie an den
Nachbarrouten als zweite Wand.
