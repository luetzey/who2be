# Phase 3 Runde 3 — Followup

Kleinpaket nach Wellen 1-5. Vorgaenger: PR #76 (merged), #77, #78. Branch:
`feat/phase-3-round3-followup`.

## Skopiert: zwei Items, die ich nach Hinterfrage behalten habe

Aus den vier urspruenglich aufgeschobenen Items bleiben **zwei**:

| Item | Status | Begruendung |
|---|---|---|
| Starter-Template fuer neue Agents | KEEP (rescoped) | Existierende 3 Seeds nutzen Liquid; ein BlockNote-Seed demonstriert die Welle-5-Architektur. |
| `unresolved_placeholders`-Tracking | KEEP | BlockNote-Path liefert die Liste heute immer leer — Defekt, nicht Polish. |
| `list_personas` MCP-Tool | DROP | Kein konkreter Use-Case; bei Bedarf nachschieben. |
| Render-Caching | DROP | Premature; aktuelle Templates sind klein, Resolver-Queries Single-Row. |

## Item A — Resolver-Refactor + unresolved-Tracking

### Datenmodell

```python
# services/placeholders/registry.py
class ResolveResult(BaseModel):
    text: str
    unresolved_key: str | None = None  # "playbook:abc-uuid" wenn Resolver fehlschlug
```

### Resolver-Protocol

```python
class PlaceholderResolver(Protocol):
    async def resolve(
        self, target_id: str, ctx: RenderContext, db: asyncpg.Connection
    ) -> ResolveResult: ...
```

### Was zaehlt als Miss

- **playbook**: ungueltige UUID, Playbook nicht im Workspace, keine
  active-Version -> `"playbook:<target_id>"`
- **resource**: dito -> `"resource:<target_id>"`
- **persona-field**: `ctx.persona_id is None`, unbekannter Feldname,
  Persona nicht gefunden -> `"persona-field:<target_id>"`
- **date**: nie miss
- **tools-overview**: nie miss

### Renderer

`render_template_body` liefert jetzt `tuple[str, list[str]]`:
- Index 0: gerenderter Plain-Text wie bisher
- Index 1: deduplizierte Liste der `unresolved_key`-Strings, lexikografisch
  sortiert (deterministisch fuer Tests)

`_walk_blocks` / `_render_block` / `_render_inline` reichen die `unresolved`-
Sammlung als Akkumulator-Liste durch (oder via context-Object — Implementier-
detail; Hauptsache reentrant).

### API-Anbindung

- `AgentRenderResponse` aus dem Liquid-Pfad hat das Feld schon
  (`unresolved_placeholders: list[str]`). Der BlockNote-Branch in
  `agent_render_service.AgentRenderService.render()` fuellt es jetzt
  ebenfalls aus dem neuen Renderer-Output.
- `AgentWithRenderedPrompt` (`/agents/{id}/rendered`, MCP `fetch_agent`)
  bekommt ein neues optionales Feld `unresolved_placeholders: list[str] = []`.
  Default leere Liste fuer Backward-Compat.

### Tests

- Pro Resolver mindestens einen Hit-Case und einen Miss-Case (UUID nicht
  vorhanden, persona_id=None, unbekanntes Feld).
- Renderer-Integrationstest: BlockNote-Doc mit 3 Pills, davon 2 Misses ->
  Plain-Text enthaelt die Fallback-Strings, `unresolved`-Liste hat genau
  die zwei `kind:target_id`-Keys, dedupliziert.
- AgentRenderService-Test fuer den BlockNote-Branch: Response enthaelt
  `unresolved_placeholders` ungleich leer wenn Targets fehlen.

## Item B — BlockNote-Starter-Template

### Migration `0027_seed_workflow_starter_template.sql`

Ein neues Default-Template `workflow-starter` (Name: „Workflow-Starter")
pro Workspace, idempotent ueber `ON CONFLICT (workspace_id, slug)` wie
0023b.

`body_format = 'blocknote'`. `body` ist `jsonb_build_array(...)` mit
ProseMirror/BlockNote-Doc-Shape:

```
H2  Rolle
P   Du bist [persona-field:name]-Pill — [persona-field:description]-Pill.
H2  Verfuegbare Werkzeuge
P   [tools-overview]-Pill
H2  So gehst du vor
UL  - Hoere der Anfrage zu und identifiziere das Thema.
    - Rufe list_triggers() auf, um zu sehen, ob ein Playbook reagiert.
    - Wenn ja: fetch_playbook(id) und folge dessen Schritten.
    - Wenn das Playbook auf eine Resource verweist: fetch_resource(id).
    - Erst wenn keines passt, antworte aus deinem allgemeinen Wissen.
H2  Letzter Stand
P   Heute ist der [date:human]-Pill.
```

Da der `body` als `text` in der DB liegt, ist `jsonb_build_array` der
falsche Hammer — der Migration-Insert schickt einen Stringified-JSON-
Literal-Wert (vorgestrichener String). Mit `E'...'`-Quoting:

```sql
INSERT INTO ... (body) VALUES (E'[{"id":"...","type":"heading","props":{"level":2}, ...}]');
```

Den exakten BlockNote-JSON-String bauen aus den Test-Shapes in
`apps/web/src/components/editor/system-prompt/SystemPromptEditor.test.tsx`
(Block-Schema mit `id`, `type`, `props`, `content`, `children`).

### Tests

- Migration-Test: nach Apply existiert das Template pro Workspace,
  `body_format='blocknote'`, `current_version=1`, `current_status='active'`.
- Renderer-Smoke gegen das Seed-Body: liefert Plain-Text mit den
  Sektionsueberschriften und der expandierten Tools-Overview-Markdown.

## Subagent-Auftrag

Ein einzelner `backend-developer`-Subagent (Sonnet, Worktree), Branch
`feat/wave6-resolver-tracking-and-starter` aus dem Worktree.

Reihenfolge: erst Item A (Renderer-Refactor + Tests), dann Item B
(Migration nutzt den neuen Renderer im Renderer-Smoke-Test). Beide in
einem PR-Strang.

Kein Frontend-Touch — `CopyPromptButton` zeigt `unresolved_placeholders`
schon korrekt an, sobald Backend es fuellt.
