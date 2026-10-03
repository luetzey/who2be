# Lernschleife C3c-1b — Liste und Zähler, Schicht 2 (Router)

Karte: t_2e50b357 (PM-Schnitt vom 2026-10-02: C3c-1a → 1b → 2a → 2b → 3).
Grundlage: C3c-1a (#792, main e8e5102d) mit
`MemoryService.list_workspace_memories` / `count_workspace_memories` und den
Modellen `MemoryFilter`, `MemoryPage`, `MemoryCounts`. Norm: ADR-0053 6.4.1.

## Outcome

`GET /v1/workspaces/{ws}/memories` und `GET /v1/workspaces/{ws}/memories/counts`
sind erreichbar, reichen Filter, `sort`, `cursor`, `limit` bzw. `group_by` an
den Service durch und tun selbst nichts weiter.

## Dateien (6 + dieser Plan)

1. `apps/api/src/who2be_api/routers/memory.py`: zwei Routen, gemeinsame
   Dependency `memory_filter` für die zehn Filter.
2. `apps/api/tests/test_memory_list_counts_api.py`: Router-Tests über HTTP.
3. `apps/api/tests/test_tenant_isolation_api.py`: zwei Proben (`agent_id` als
   Objekt-Referenz → V1 und V2).
4. `apps/api/tests/contract/openapi_surface.json`: Golden.
5. `docs/reference/openapi.json`: Export.
6. `changelog.d/t-2e50b357-lernschleife-c3c-1b-liste-zaehler-router.added.md`.

`tests/contract/gate_inventory.json` aus dem Kartenumfang bleibt unverändert:
das Inventar erfasst nur POST-Routen (`test_gate_inventory.py`), beide neuen
Routen sind GET.

## Vorentschiedene Weichen (Beleg im Repo)

- Cursor über die vorhandene Dependency `core.pagination.PageCursor`
  (ungültig → 422 `invalid_cursor`), wie `tokens.py` u. a. Anders als dort
  steht `next_cursor` im Body (`MemoryPage` aus C3c-1a), nicht im Header
  `X-Next-Cursor` — das Modell ist mit C3c-1a gemergt und freigegeben.
- `limit` 1..`MEMORY_LIST_LIMIT_MAX` (50) als Query-Grenze, also 422 statt
  stiller Kappung; Standard `MEMORY_LIST_LIMIT_DEFAULT` (20).
- `created_after` als `AwareDatetime`: ohne Zeitzone 422 der Anfrage (wie der
  Validator in `MemoryFilter`), nie ein 500 beim Bau des Modells.
- `group_by` als wiederholbarer Query-Parameter (`?group_by=a&group_by=b`).
- Rate-Limit: keins, wie die übrigen menschlichen Lese-Routen des Routers
  (`/memory-proposals`, `/me/memories`); `enforce_mcp_read_limit` gilt nur für
  agent-gerichtete Reads, und Agent-Tokens sind hier 403.

## Verifikation

- `uv run ruff check . && uv run ruff format --check . && uv run mypy .`
- Router-, Isolations-, Gate-Inventar- und OpenAPI-Vertragstest gezielt
- volle DoD laut CONTRIBUTING.md auf frischer DB
- Rot-Proben: Sichtbarkeitsklausel im Repository entschärft; `limit`-Grenze
  auf 51; Cursor nicht durchgereicht; `group_by` nicht durchgereicht; `q`
  nicht durchgereicht; Agent-Prüfung im Service entfernt (Isolationstest).

## Review-Runde 1 (Changes requested) — Nachtrag

Befund @reviewer: `origin`, `source`, `health`, `held` und `created_after`
waren über HTTP nicht belegt; Mutanten (Parameter in `memory_filter()` fest
auf `None`) blieben grün, `created_after=2020-01-01` filterte nichts.

Abhilfe (nur Testdatei): Helfer `Env.memory` bekommt `origin`, `source` und
`confirmed`; neuer Test `test_filter_origin_source_health_held_created_after`
mit Daten, in denen jeder der fünf Filter eine echte Teilmenge liefert (Liste
und `/memories/counts`), `created_after` liegt zwischen zwei Einträgen.
Rot-Probe: dieselbe Mutation je Parameter — 5/5 Mutanten rot.
