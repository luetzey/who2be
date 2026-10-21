# Navigation W2-api (A4): `GET /agents/{agent_id}/work-areas`

Karte t_1371bfba. Basis `origin/main` @ `e730f3ad`. Spec
`navigation-transparenz-design-2026-10.md` §3.1 (Ueberblick, Block
„Arbeitsbereiche"), §5 A4. PM-Entscheidung 2026-10-10: Schnitt S1 (nur A4,
A6 → t_c84f1dd3), Weiche W1.

## Vertrag

`GET /v1/workspaces/{ws}/agents/{agent_id}/work-areas` → `list[AgentWorkAreaRead]`

| Feld | Bedeutung |
|---|---|
| `id`, `name`, `scope` | Area |
| `level` | Grant-Stufe DIESES Agenten (`read`/`write`) |
| `owner` | `true` = private Area dieses Agenten („eigener") |
| `agent_count` | Zahl der Grants an der Area (alle Agenten, inkl. diesem) |

- Quelle: materialisierte Grants (`work_area_grant`) des Agenten; eine private
  Area entsteht erst beim ersten Agent-Zugriff (leere Liste davor).
- Rechte (W1): nur Menschen (JWT). Agent-gebundene Tokens 403
  `missing_capability` (agent_count verraet fremde Agenten, Muster
  Grant-Liste); ungebundene Tokens 403 ueber die Router-Sperre
  `require_agent_bound_token` (Route liegt im work_areas-Router).
- Sichtbarkeit: `readable_area_ids` — viewer nur shared, editor+ auch privat.
- Unbekannter oder workspace-fremder Agent: 404 `agent_not_found`.
- Sortierung: privat zuerst, dann Name, id (wie whoami).

## Dateien (Budget 8, ohne Plan und generierte Artefakte)

1. `packages/models/src/who2be_models/workarea.py` (+`AgentWorkAreaRead`, Import aus Submodul)
2. `apps/api/src/who2be_api/repositories/work_area_repository.py` (+`list_for_agent`)
3. `apps/api/src/who2be_api/services/work_areas.py` (+`list_for_agent`)
4. `apps/api/src/who2be_api/routers/work_areas.py` (+Route)
5. `apps/api/tests/test_agent_work_areas_api.py` (neu: Rollen, Token-Arten, 404, agent_count/owner, RLS unter `who2be_app`)
6. `apps/api/tests/test_tenant_isolation_api.py` (Inventar-Probe)
7. `changelog.d/t-1371bfba-agent-work-areas.added.md`

Generiert: `docs/reference/openapi.json`, `apps/api/tests/contract/openapi_surface.json`.

## Verifikation

DoD aus CONTRIBUTING.md (ruff, format, mypy, pytest mit DB + Coverage, Lizenz,
effectful-tests). Fotos: entfaellt, keine sichtbare UI-Aenderung.
