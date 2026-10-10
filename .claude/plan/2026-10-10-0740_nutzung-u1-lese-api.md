# Nutzung U1: Lese-API Zähler je Element

Karte t_83dad727. Basis `origin/main` @ `2aac9124`. Konzept
`nutzungszaehler-konzept-2026-10.md` §5.1, §5.4, §7 (U1). Owner Z1a: gezählt
werden nur Auslieferungen an Agenten (`usage_event.source = 'server'`).

## Vertrag

`GET /v1/workspaces/{ws}/usage/{entity_type}/{entity_id}` → `UsageStats`
`GET /v1/workspaces/{ws}/usage?entity_type=` → `UsageList`

| Feld | Bedeutung |
|---|---|
| `uses_7d`, `uses_30d` | Auslieferungen in den letzten 7 bzw. 30 Kalendertagen (UTC), heute eingeschlossen |
| `last_used_at` | jüngste Auslieferung überhaupt (nicht nur im Fenster), sonst `null` |
| `distinct_agents_30d` | verschiedene Agenten in den 30 Tagen |
| `daily` | nur Einzelsicht: 30 Einträge `{day, uses}`, ältester zuerst, lückenlos mit 0 |
| `counting_since` | fest `2026-10-08` (Deploy D3 #856); ältere Zeilen sind `agent_report` und zählen nicht |

- `entity_type` ∈ {persona, playbook, resource} (nur die zeichnet der Server auf).
- Fenster sind Kalendertage in UTC, damit `uses_30d == sum(daily)` gilt.
- Liste: ohne `entity_type` alle drei Typen; je Element eine Zeile, auch mit 0
  (gelöschte Elemente fallen über den Element-Join heraus). Keine Tagesreihe in
  der Liste (Gewicht; Mini-Verlauf ist Einzelsicht).
- Rechte: ab viewer (Spec §3.2 „Nutzung · ab viewer"); reine Zähler, kein
  Personenbezug. Fremdes/unbekanntes Element → 404 `feedback_element_not_found`.
- `feedback-overview`: additiv `last_used_at` (nur `source='server'`) und
  `last_feedback_at`; `last_activity_at` bleibt unverändert (Back-Compat).

## Last / Index

Keine Migration. Abfragen laufen je Element über `usage_event_entity_idx`
`(workspace_id, entity_type, entity_id, created_at DESC)`; die Liste geht von der
Element-Tabelle aus (LATERAL je Element) und wächst mit Elementzahl × Fenster,
nicht mit der Gesamthistorie. Nachweis per `EXPLAIN ANALYZE` auf synthetischen
Daten (Ergebnis im PR-Body). Nur wenn der Plan einen Seq Scan zeigt: needs_input.

## Dateien (Budget 8, ohne Plan und generierte Dateien)

1. `packages/models/src/who2be_models/feedback.py`
2. `packages/models/src/who2be_models/__init__.py`
3. `apps/api/src/who2be_api/repositories/feedback_repository.py`
4. `apps/api/src/who2be_api/services/feedback_service.py`
5. `apps/api/src/who2be_api/routers/feedback.py`
6. `apps/api/tests/test_usage_stats_api.py` (neu)
7. `apps/api/tests/test_tenant_isolation_api.py`
8. `changelog.d/t-83dad727-usage-stats.added.md`

Generiert: `docs/reference/openapi.json`, `apps/api/tests/contract/openapi_surface.json`.

## Verifikation

DoD aus CONTRIBUTING.md (ruff, format, mypy, pytest mit DB + Coverage, Lizenz,
effectful-tests). Rot-Probe: `source='server'`-Filter entfernen → Tests rot.
Fotos: entfällt, keine sichtbare UI-Änderung.
