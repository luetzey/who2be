# Navigation W1-api: `GET /inbox/counts[?agent_id]`

Karte t_cfd81259. Basis `origin/main` @ `6858f707`. Spec
`navigation-transparenz-design-2026-10.md` §2.2, §2.6 a, §5 A1; Weichen N1 a,
N3 a (PM 2026-10-09).

## Vertrag

`GET /v1/workspaces/{ws}/inbox/counts[?agent_id=]` → `InboxCounts`
(`packages/models/.../inbox.py`). Rein lesend, keine Tabelle (N1 a).

| Feld | Quelle | viewer | editor | admin | in `total` |
|---|---|---|---|---|---|
| `follow_ups_due` | Massnahmen, Nachschau-Datum ≤ heute (UTC), Zustand weder eingestuft noch zurueckgezogen | null | Zahl | Zahl | ja |
| `memory_approval` | `status=pending` + offene Vorschlaege (= `countApprovalQueue`) | eigenes Nutzergedaechtnis | Zahl | Zahl | ja |
| `versions_review` | aktuelle Version `review` (Persona/Playbook/Resource) | null | Zahl | Zahl | nur admin |
| `system_prompts_review` | System-Prompt-Templates `review` | null | Zahl | Zahl | nur admin |
| `cases_open` | Faelle `open`+`reopened` | null | Zahl | Zahl | ja |
| `patterns` | `GET /patterns` (Laenge) | null | Zahl | Zahl | nie |

- `null` = fuer diese Rolle keine Art (die Seite blendet den Abschnitt aus),
  `0` = Art sichtbar, nichts offen.
- `total` = Glockenzahl nach §2.2.
- `agent_id`: fremd/unbekannt → 404 `agent_not_found`. Versionen und
  System-Prompts sind keinem Agenten eindeutig zuzuordnen → mit `agent_id`
  `null` (Entscheidung, belegt durch §3.1 Aufgaben-Zeile ohne Versionen).
- Nur Menschen (agent-gebundene Tokens 403, wie die Memory-Verwaltung und
  N10 a).
- Jede Zahl ueber die bestehenden Services (dieselbe Sichtbarkeit wie die
  Listen); neu ist nur die Faellig-Zaehlung im `session_repository`.

## Dateien (Budget 8, ohne Plan und generierte Artefakte)

1. `packages/models/src/who2be_models/inbox.py` (neu)
2. `apps/api/src/who2be_api/repositories/session_repository.py` (+`count_due_measures`)
3. `apps/api/src/who2be_api/services/inbox_service.py` (neu)
4. `apps/api/src/who2be_api/routers/inbox.py` (neu)
5. `apps/api/src/who2be_api/main.py` (Mount)
6. `apps/api/tests/test_inbox_counts_api.py` (neu: je Rolle, agent_id, Faellig-Regel, RLS als `who2be_app`, fremder Workspace)
7. `changelog.d/t-cfd81259-inbox-counts.added.md`

Generiert: `docs/reference/openapi.json`, `apps/api/tests/contract/openapi_surface.json`.

## Verifikation

DoD aus CONTRIBUTING.md (ruff, format, mypy, pytest mit DB + Coverage, Lizenz,
effectful-tests). Fotos: entfaellt, keine sichtbare UI-Aenderung.
