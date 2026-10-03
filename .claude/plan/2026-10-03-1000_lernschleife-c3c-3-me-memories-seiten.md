# Lernschleife C3c-3 — `GET /me/memories` mit `q`, `cursor`, `limit`

Karte: t_864de535 (PM-Schnitt 2026-10-02: C3c-1a → 1b → 2a → 2b → 3).
Basis: origin/main 4c1576e9 (C3c-2b #797 gemergt). Norm: ADR-0053 6.4.1,
Zeile `GET /me/memories` („wie 6.4, zusätzlich mit `q`, `cursor`, `limit`“).

## Outcome

Das eigene Nutzergedächtnis ist über `GET /me/memories?status&q&cursor&limit`
durchsuch- und seitenweise abrufbar, mit dem Filterbau aus C3c-1a
(`_memory_where` / `list_visible`). Nur eigene Einträge, kein
Personen-Parameter.

## Akzeptanzkriterien

- `q` = ILIKE-Teilstring über `fact` (wie `GET /memories`, inkl. Escaping).
- Keyset-Cursor auf `(created_at, id)`, opak; ungültig → 422 `invalid_cursor`.
- `limit` 1..50 (422 außerhalb), Standard 20 — wie `GET /memories`.
- Nur eigene Einträge: weder fremdes Nutzergedächtnis (auch admin nicht) noch
  Agentengedächtnis (auch editor nicht). Rot-Probe belegt.
- CI 17/17, volle DoD auf frischer DB.

## Out of Scope

Web; `sort` (steht für `/me/memories` nicht im ADR, Reihenfolge bleibt
„neueste zuerst“ wie bisher).

## Dateien (8 + dieser Plan)

1. `apps/api/src/who2be_api/routers/memory.py` — Query-Parameter, Antwort `MemoryPage`.
2. `apps/api/src/who2be_api/services/memory_service.py` — `list_my_memories`
   über `list_visible` mit Sicht „nur eigenes Nutzergedächtnis“.
3. `apps/api/src/who2be_api/repositories/memory_repository.py` — totes
   `list_for_user` (Protokoll + Implementierung) entfernt.
4. `apps/api/tests/test_memory_proposal_api.py` — Bestandstests auf
   `MemoryPage`, neuer Test für `q`/`cursor`/`limit` und Isolation.
5. `apps/api/tests/test_memory_proposals.py` — Service-Test auf `MemoryPage`.
6. `apps/api/tests/test_memory_revoke_auto_api.py` — eine Zusicherung auf
   `MemoryPage` (im ersten DoD-Lauf gefunden: f-String-Pfad, von der
   Vorab-Suche nicht erfasst).
7. `docs/reference/openapi.json` — Export.
8. `changelog.d/t-864de535-lernschleife-c3c-3-me-memories-seiten.added.md`.

8 Dateien + dieser Plan (Prozessartefakt, wie bei #795/#797).

`openapi_surface.json` (operationId unverändert), `gate_inventory.json` (nur
POST) und die Isolationsprobe (`GET /me/memories` ohne Objekt-Referenz)
bleiben unverändert.

## Vorentschiedene Weichen (Beleg im Repo)

- Antwortform `MemoryPage` (`items`, `next_cursor` im Body) statt Liste mit
  Header `X-Next-Cursor`: gleiche Form wie `GET /memories` (C3c-1b, Plan
  2026-10-03-0215). Bruch der Liste ist unkritisch: `/me/memories` kam mit
  C3b und steht nur in `changelog.d/` (unveröffentlicht), kein Konsument in
  `apps/web` oder `packages`.
- Sicht: `MemoryVisibility(viewer_user_id=ctx.user_id, include_agent_scope=False)`
  plus `MemoryFilter(scope=user)` — dieselbe SQL wie `GET /memories`, aber
  ohne Agentengedächtnis auch für editor. Die Warteschlangen-Regel
  (`pending` ohne `lesson`) ist hier wirkungslos, weil Nutzergedächtnis per
  DB-CHECK immer `kind='user_fact'` ist (0091 `agent_memory_user_scope_check`).
- Rechte unverändert über `_owner(ctx, None)` (viewer, human-only).

## Schritte

1. [x] Service + Repository (`list_my_memories` über `_page`, gemeinsam mit
   `list_workspace_memories`; `list_for_user` entfernt, kein weiterer Aufrufer).
2. [x] Router.
3. [x] Tests anpassen und neuen Test `test_me_memories_suche_und_seiten` schreiben.
4. [x] OpenAPI-Export, Changelog.
5. [x] Rot-Proben 5/5 rot: R1 `include_agent_scope=True` ohne `scope=user`
   (Agentengedächtnis-Leck) → neuer Test rot; R2 Sichtklausel in
   `_memory_where` auf „jedes Nutzergedächtnis“ → neuer Test und
   `test_admin_sieht_fremdes_nutzergedaechtnis_nicht` rot; R3 `q` nicht
   durchgereicht → rot; R4 Cursor nicht durchgereicht → rot (zuerst
   Endlosschleife, deshalb Seitenobergrenze im Test ergänzt); R5 `limit`-Grenze
   51 → rot. Quelltext danach im Zielzustand, Export ohne Drift.
6. [x] Volle DoD auf frischer DB (`who2be_c3c3_dod4`): ruff, format, mypy
   (536 Dateien) grün; pytest --cov 2823 passed, 0 skipped, 93,35 %;
   Skip-Budget 0/0; Lizenz-Gate ok; Wirkungs-Prüfung ok. Erster Lauf (dod3)
   fand die übersehene Zusicherung in `test_memory_revoke_auto_api.py`.

## Verifikation

- `uv run ruff check . && uv run ruff format --check . && uv run mypy .`
- `pytest apps/api/tests/test_memory_proposal_api.py apps/api/tests/test_memory_proposals.py`
- volle DoD laut CONTRIBUTING.md auf frischer DB
