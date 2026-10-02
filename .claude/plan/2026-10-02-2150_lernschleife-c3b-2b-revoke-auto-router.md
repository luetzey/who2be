# Lernschleife C3b-2b — Not-Aus, Schicht 2 (Router)

Karte: t_dc59cec6 (PM-Schnitt B). Grundlage: C3b-2a (#789, main 8d73bada) mit
`MemoryService.revoke_auto`, Modellen und `memory_batch_count_mismatch`.
Norm: ADR-0053 6.4.1 „Notfall-Rücknahme“.

## Outcome

`POST /v1/workspaces/{ws}/memories/revoke-auto` ist erreichbar, ruft nur
`MemoryService.revoke_auto` und liefert je nach `dry_run` die Vorschau
(`count, sample, hidden_count`) oder das Ergebnis (`count, hidden_count, results`).

## Dateien (7 + dieser Plan)

1. `apps/api/src/who2be_api/routers/memory.py`: Endpunkt, dünn, `write_limit`.
2. `apps/api/tests/test_memory_revoke_auto_api.py`: Router-Tests über HTTP.
3. `apps/api/tests/test_tenant_isolation_api.py`: Probe (dry_run, `agent_id`
   als Objekt-Referenz → V1 und V2).
4. `apps/api/tests/contract/gate_inventory.json`: `ungated`-Zeile mit Begründung.
5. `apps/api/tests/contract/openapi_surface.json`: Golden.
6. `docs/reference/openapi.json`: Export.
7. `changelog.d/t-dc59cec6-lernschleife-c3b-2b-revoke-auto-router.added.md`.

## Vorentschiedene Weichen

- Ein Endpunkt, Antworttyp als Union aus Vorschau und Ergebnis (der Service
  liefert genau diese Union; `dry_run` entscheidet). Status 200 in beiden Fällen,
  weil nichts angelegt wird.
- Rate-Limit `write_limit` wie jede mutierende Memory-Route.
- Isolationsprobe mit `dry_run=true`: die Gegenprobe soll den Bestand von B
  nicht verändern; die Mandantengrenze prüft `agent_id` (V2) und `wsB` (V1).

## Verifikation

- `uv run ruff check . && uv run ruff format --check . && uv run mypy`
- Router-Test, Isolations-, Gate-Inventar- und OpenAPI-Vertragstest gezielt
- volle DoD laut CONTRIBUTING.md auf frischer DB
- Rot-Proben: Admin-Inhalt im Ergebnis (Filter weg), viewer zugelassen,
  Zählvergleich weg.
