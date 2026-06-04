# Embed-Modus (lazy/inline) + Resource→Resource im UI

Branch: `feat/embedding-mode-resource-compose`

## Ziel

1. **Embed-Modus** pro Einbettung (playbook→resource, resource→resource):
   `embedding_mode` ∈ {`lazy`, `inline`}, Default **`lazy`**. Nur `inline`-Links
   werden vom MCP-Server inline mitgesendet; `lazy`-Links bleiben reine Pointer
   (der Agent laedt via `fetch_*` nach). **Bewusst breaking**: bestehende
   `resource`-scope-Links wurden bisher immer inline geliefert, sind nun
   standardmaessig lazy.
2. **Resource→Resource im UI**: SubResourcePicker (war bereits in der
   ResourceDetailPage verdrahtet) um den Embed-Modus-Toggle ergaenzt.

## Umsetzung

- **Migrationen** (reserviert 0040/0041):
  - `0040_link_embedding_mode.sql` — Spalte `embedding_mode TEXT NOT NULL
    DEFAULT 'lazy'` + CHECK auf `playbook_resource_link`.
  - `0041_composition_embedding_mode.sql` — gleiche Spalte auf
    `resource_composition` und (Schema-Vorbereitung) `persona_playbook`.
- **Models** (`packages/models/resource.py`): `EmbeddingMode`-Alias; Feld auf
  `ResourceLinkItem`, `ResourceLinkRead`, `SubResourceLinkItem`,
  `SubResourceRead`; neues `ResourceRead.inline_sub_resources`. Barrel-Export.
- **Repos**: `playbook_resource_link_repository` + `resource_composition_repository`
  schreiben/lesen `embedding_mode`.
- **MCP** (`apps/mcp/server.py`):
  - `fetch_playbook`: inline nur bei `link_scope='resource'` UND
    `embedding_mode='inline'`.
  - `fetch_resource`: `inline`-Sub-Resources zusaetzlich als Volldokument in
    `inline_sub_resources` (eine Ebene); `lazy` bleibt Pointer in
    `sub_resources`.
- **Frontend** (`features/playbooks` + `features/resources`):
  - `ResourceBlockLinkPicker`: Modus-Toggle „Link (lazy)“/„Fest einbetten“ fuer
    den „Gesamtes Dokument“-Scope.
  - `SubResourcePicker`: Modus-Toggle je ausgewaehlter Sub-Resource.
  - `LinkedBlocksList` + `ResourceDetailPage`: Modus-Anzeige.

## DoD

- `uv run pytest -q`, `ruff`, `mypy` gruen (DB-Tests skippen ohne DB).
- `npm run lint`, `npx tsc --noEmit`, `npm test`, `npm run build` gruen.
- MCP-Tests: lazy NICHT inline, inline schon (playbook + resource).
