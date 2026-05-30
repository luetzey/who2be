# Phase-3-Fixes — Track 4: Playbook→Resource Link-Scope

Status: in Arbeit (2026-05-29).

Bezugsdokumente:

- Phase-3-Master: `.claude/plan/2026-05-29-1900_phase-3-ux-polish.md`
- Phase-3-A Backend (Section-Block-Refs): `.claude/plan/2026-05-29-1850_3-A-backend.md`
- Phase-3-B Editor/Forms: `.claude/plan/2026-05-29-1851_3-B-editor-forms.md`
- ADR-0021 (Block-Refs Playbook→Resource)

## Hintergrund

Stand Phase 3-A erlaubt `playbook_resource_link` ausschliesslich Block-Refs auf
einzelne Heading-Anker (PK `(playbook_id, resource_id, block_id)`,
Heading-Only-Validator im Service). In der Praxis fehlt der Fall „Playbook
referenziert eine **ganze** Resource als Wissensquelle", ohne dass ein
spezifischer Abschnitt gemeint ist. Track 4 ergaenzt diesen Modus.

## Ziel

Ein Playbook kann eine Resource entweder

- als **Gesamtdokument** (`link_scope='resource'`, `block_id` IS NULL,
  exakt ein solcher Link je `(playbook_id, resource_id)`), oder
- als **einzelnen Block-Anker** (`link_scope='block'`, `block_id` ist
  Heading-ID; mehrere je `(playbook_id, resource_id)` erlaubt)

verlinken. Der MCP-Tool-Aufruf `fetch_playbook` liefert den passenden
Inhalt zurueck — Volltext fuer 'resource', Section-Snippet fuer 'block'.

## Scope

### DB

`apps/api/src/who2be_api/migrations/0021_playbook_resource_link_scope.sql`:

- `block_id` von `NOT NULL` auf nullable; ALTER PRIMARY KEY entfernen.
- Neue Spalte `link_scope text NOT NULL DEFAULT 'block'
  CHECK (link_scope IN ('resource','block'))`.
- Backfill: alle Bestandszeilen → `link_scope='block'` (DEFAULT erledigt das
  beim `ADD COLUMN`).
- Sanity-Constraint:
  `(link_scope='resource' AND block_id IS NULL)
   OR (link_scope='block' AND block_id IS NOT NULL)`.
- Partielle Unique-Indexe:
  - `(playbook_id, resource_id) WHERE link_scope='resource'`
  - `(playbook_id, resource_id, block_id) WHERE link_scope='block'`
- Idempotenz wie 0019/0020: `IF NOT EXISTS`-Probe in `DO $$`-Bloecken.

### Models (`packages/models/src/who2be_models/resource.py`)

- `ResourceLinkItem` (Eingabe):
  - `link_scope: Literal['resource','block'] = 'block'` (Default = Backward-Compat).
  - `block_id: BlockId | None` (statt required).
  - `model_validator` (after): scope='resource' → block_id MUST be None;
    scope='block' → block_id MUST be set.
- `ResourceLinkRead` (Ausgabe):
  - `link_scope: Literal['resource','block'] = 'block'`.
  - `block_id: str | None`.
- `LinkedBlockSection` erbt mit; Section-Felder bleiben optional (leer fuer
  'resource').

### Backend

`apps/api/src/who2be_api/repositories/playbook_resource_link_repository.py`:

- `list_links` waehlt `link_scope`, `block_id` mit aus; fuer 'resource' wird
  kein Section-Match versucht, `preview`/`section_*` bleiben `None`/`[]`;
  `available_in` markiert die genutzte Version anhand `resource_version`.
- `set_links` INSERTed `link_scope` mit; bei 'resource' wird `block_id` als
  `NULL` uebergeben.
- Konflikt mit DELETE-ALL-bei-Set bleibt — wir loeschen weiterhin den
  Komplettstand, dafuer kollidieren Unique-Indexe nicht mit
  Set-Replace-Semantik.

`apps/api/src/who2be_api/services/playbook_resource_link_service.py`:

- Dedup-Key: `(resource_id, link_scope, block_id)` (NULL-tolerant).
- Heading-Validator wirkt nur fuer 'block'-Items (mit non-NULL block_id).
- Modell-Validator faengt Mismatch frueh ab (422 via Pydantic).

### MCP

`apps/mcp/src/who2be_mcp/server.py`:

- `fetch_playbook` reichert `linked_blocks` an: pro 'resource'-Link wird die
  Resource via `get_resource` geladen und als `LinkedResourceDoc` (oder
  Erweiterung) angehaengt; pro 'block'-Link bleibt das bisherige
  Section-Verhalten (Pointer + Section-Preview im ResourceLinkRead).
- Response-Shape `PlaybookWithResources`:
  - bisher `linked_blocks: list[ResourceLinkRead]`.
  - kuenftig zusaetzlich `linked_resources: list[ResourceRead]` — eine
    deduplizierte Liste der Volldokumente, auf die scope='resource'-Links
    zeigen. Block-Links bleiben Pointer (Backward-Compat zum Client; ADR-0021).

Tests: `apps/mcp/tests/test_resource_tools.py`:

- 'resource'-Link → `linked_resources` enthaelt Volltext, `linked_blocks`
  enthaelt den Pointer mit `link_scope='resource'`, `block_id=None`.
- 'block'-Link → `linked_blocks` enthaelt Section-Pointer wie bisher,
  `linked_resources` ist leer.

### Frontend

`apps/web/src/api/types.ts`:

- `ResourceLink` + `ResourceLinkItemInput` um
  `link_scope?: 'resource' | 'block'` und `block_id: string | null` erweitern.

`apps/web/src/features/playbooks/components/ResourceBlockLinkPicker.tsx`:

- Pro Resource ein Toggle „Gesamtes Dokument verknuepfen" (Checkbox).
- Aktiv: Block-Checkboxen disabled + visuell ausgegraut; Speichern erzeugt
  einen 'resource'-Link.
- Save mappt selected → Items mit korrektem `link_scope`/`block_id`.

`apps/web/src/features/playbooks/components/LinkedBlocksList.tsx`:

- Fuer `link_scope='resource'`: Badge „Ganzes Dokument" + Sub-Label
  „Vollstaendige Resource referenziert"; kein Section-Preview.

### Tests

- Pytest (`apps/api/tests/test_playbook_resources.py`):
  - Migration-Forward bleibt durch `_prepare_db()` abgedeckt; neuer
    Test-Case `test_resource_links_resource_scope_roundtrip` deckt
    Set+Get fuer 'resource' ab.
  - `test_resource_links_resource_scope_unique` — zweiter 'resource'-Link
    wird durch Dedup im Service auf einen reduziert (Acceptance).
  - `test_resource_links_resource_and_block_coexist` — beide Scopes neben-
    einander erlaubt.
- Vitest:
  - `ResourceBlockLinkPicker.test.tsx`: Toggle „Gesamtes Dokument" disabled
    die Checkboxes, Save liefert `link_scope='resource'`.
  - `LinkedBlocksList.test.tsx`: 'resource'-Link rendert „Ganzes Dokument".

## Acceptance

- Bestehende Block-Links bleiben funktional nach Migration (Bestand →
  scope='block', `block_id` unveraendert).
- Genau ein 'resource'-Link pro `(playbook, resource)` zugelassen, ueber
  Backend-Dedup + DB-Unique abgesichert.
- MCP-`fetch_playbook` haengt Resource-Volltext fuer 'resource'-Links,
  Section-Snippet fuer 'block'-Links an.
- Picker zeigt Toggle pro Resource, exklusiv zu den Block-Checkboxen.

## DoD

- `uv run ruff check . && uv run mypy . && uv run pytest -q` — gruen.
- `npm run lint && npx tsc --noEmit && npm test && npm run build` — gruen.
- Migration laeuft sowohl auf frischer Test-DB als auch idempotent ueber
  Bestandsdaten (`_prepare_db()` im Integrationstest deckt das ab).

## Branch

`feat/playbook-resource-link-scope` (vom User vorgegeben; Cloud-Session
arbeitet auf `claude/modest-meitner-4edNo` und merged nach
`feat/playbook-resource-link-scope` oder direkt in den PR-Branch).
