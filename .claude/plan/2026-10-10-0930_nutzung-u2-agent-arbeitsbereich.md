# Nutzung U2: Agent- und Arbeitsbereich-Zähler

Karte t_7d6ca780. Basis `origin/main` @ `39ec4d2e` (U1 #903). Konzept
`nutzungszaehler-konzept-2026-10.md` §3, §5.2, §5.3, §7 (U2). Owner Z1a (nur
Auslieferungen an Agenten), Z2a (Agent-Zähler aus vorhandenen Daten, kein
`fetch_agent`-Zähler). Keine Migration.

## Vertrag

`GET /v1/workspaces/{ws}/agents/{agent_id}/usage` → `AgentUsageStats`

| Feld | Bedeutung |
|---|---|
| `uses_7d`, `uses_30d` | Auslieferungen (`usage_event`, `source='server'`) an diesen Agenten, Kalendertage UTC wie U1 |
| `uses_by_type_30d` | `{persona, playbook, resource}` im 30-Tage-Fenster |
| `active_days_30d` | Tage im Fenster mit mindestens einer Auslieferung |
| `last_used_at` | jüngste Auslieferung überhaupt |
| `last_active_at` | `max(api_token.last_used_at)` über alle Tokens des Agenten (auch widerrufene) |
| `daily` | 30 Einträge `{day, uses}` |
| `work_areas` | je Arbeitsbereich mit Zugriff dieses Agenten: `area_id`, `access_days_30d`, `last_access_on` (Datum) |
| `counting_since` | 2026-10-08 (wie U1) |

`GET /v1/workspaces/{ws}/work-areas/{area_id}/usage` → `WorkAreaUsageStats`

| Feld | Bedeutung |
|---|---|
| `access_days_30d` | verschiedene Tage im Fenster mit mindestens einem Zugriff |
| `accesses_30d`, `reads_30d`, `writes_30d` | Log-Einträge (Agent, Element, Operation, Tag) im Fenster |
| `distinct_agents_30d` | verschiedene Agenten im Fenster (nur Zahl) |
| `last_access_on` | jüngstes `access_date` überhaupt — Datum, keine Uhrzeit |
| `daily` | 30 Einträge `{day, accesses}` |

Zuordnung Log → Bereich über `wa_artifact.area_id` (`ref_kind='artifact'`) und
`wa_table.area_id` (`ref_kind='table'`). Blob und KB-Knoten haben keinen
Bereich und fallen heraus (Konzept O4). Gelöschte Artifacts/Tabellen ebenso.

## Rechte (wie U1, PM-Hinweis)

- ab viewer; agent-gebundene Tokens 403 `missing_capability`.
- keine Agent-Namen in den Antworten, nur IDs/Zahlen.
- Sichtbarkeit Bereiche wie `readable_area_ids` für Menschen: viewer nur
  shared, editor+ auch private. Unsichtbar/unbekannt/fremd → 404
  `area_not_found`; Agent unbekannt/fremd → 404 `agent_not_found`.
- `work_areas` im Agent-Zähler wird genauso gefiltert.

## Weichen (aus dem Repo entschieden)

- Pfade unter `/agents/{id}/usage` und `/work-areas/{id}/usage` statt
  `/usage/agents/{id}`: kollidiert sonst mit `/usage/{entity_type}/{entity_id}`
  (U1) und folgt dem Muster `/agents/{id}/work-areas` (A4). Router bleibt
  `routers/feedback.py` (Nutzungszähler-Heimat aus U1, Dateibudget).
- Aktive Tage nur aus `usage_event` (Konzept §3-Tabelle), nicht aus dem
  Zugriffslog — Bereichszugriffe stehen getrennt in `work_areas`.
- Keine Listen-Endpunkte (`/usage/agents`): Listenspalten sind U4.

## Dateien (Budget 8, ohne Plan und generierte Dateien)

1. `packages/models/src/who2be_models/feedback.py`
2. `packages/models/src/who2be_models/__init__.py`
3. `apps/api/src/who2be_api/repositories/feedback_repository.py`
4. `apps/api/src/who2be_api/services/feedback_service.py`
5. `apps/api/src/who2be_api/routers/feedback.py`
6. `apps/api/tests/test_usage_agent_area_api.py` (neu)
7. `apps/api/tests/test_tenant_isolation_api.py`
8. `changelog.d/t-7d6ca780-usage-agent-area.added.md`

Generiert: `docs/reference/openapi.json`, `apps/api/tests/contract/openapi_surface.json`.

## Verifikation

DoD aus CONTRIBUTING.md. Rot-Probe: `source='server'`-Filter im Agent-Zähler
entfernen → Test rot. Fotos: entfällt, keine sichtbare UI-Änderung.
