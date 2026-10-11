# Navigation W2-api-b (A6): `GET /feedback-overview?agent_id=&days=`

Karte t_c84f1dd3. Basis `origin/main` @ `31b5fc5c`. Spec
`navigation-transparenz-design-2026-10.md` §3.2, §5 A6 (Kachel „Feedback zu
seinen Bausteinen · 30 Tage"). Abgespalten aus t_1371bfba (Schnitt S1).

## PM-Entscheidungen (2026-10-10, Wortlaut)

- W2: Rechte bleiben editor+ wie heute. Keine Rechteänderung; die Kachel
  entfällt für viewer (Spec §3.2 „Kacheln ohne Recht entfallen").
- W3: zusätzlicher optionaler Parameter `days` (1..365) am selben Endpunkt;
  ohne `days` unverändert Gesamtsumme.
- `agent_id` filtert `usage_event` und `agent_feedback` auf Ereignisse dieses
  Agenten; unbekannter oder fremder Agent → 404 `agent_not_found`.

## Vertrag

`GET /v1/workspaces/{ws}/feedback-overview` — Antwortform `FeedbackOverview`
unverändert.

| Parameter | Typ | Wirkung |
|---|---|---|
| `agent_id` | uuid, optional | nur Zeilen mit `agent_id = <id>` in beiden Tabellen |
| `days` | int 1..365, optional | nur Zeilen mit `created_at >= now() - days` |

- Reihenfolge der Prüfungen: Rolle (editor+, sonst 403) → Agent existiert im
  Workspace (sonst 404 `agent_not_found`) → Aggregat.
- `days` außerhalb 1..365 → 422 (FastAPI-Validierung).
- Ohne Parameter: identische SQL-Semantik wie bisher (Filter sind
  `$n IS NULL OR …`).
- 404-Helper: `core.workarea_scope.agent_not_found` (eine Quelle für den Grund).

## Dateien (Budget 8)

1. `apps/api/src/who2be_api/routers/feedback.py`
2. `apps/api/src/who2be_api/services/feedback_service.py`
3. `apps/api/src/who2be_api/repositories/feedback_repository.py`
4. `apps/api/tests/test_feedback_overview_filters.py` (neu)
5. `changelog.d/t-c84f1dd3-feedback-overview-agent-days.added.md`
6. dieser Plan

Generiert: `docs/reference/openapi.json`. Keine neue Route → kein
Inventar-/Surface-Eintrag.

## Verifikation

DoD aus CONTRIBUTING.md (ruff, format, mypy, pytest mit DB + Coverage, Lizenz,
effectful-tests). Rot-Probe: Filter im Repository auskommentieren → neue Tests
rot. Fotos: entfällt, keine sichtbare UI-Änderung.
