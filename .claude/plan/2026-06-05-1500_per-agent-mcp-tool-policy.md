# Per-Agent MCP-Tool-Policy (Capability-Gates + Read-Scoping)

Stand: 2026-06-05 · Branch `claude/nifty-brahmagupta-IhSzs`

## Ziel (User-Request)

Pro Agent konfigurierbar, welche MCP-Tools er nutzen darf:

- **Reads** standardmaessig „alles sehen" (Read-All), pro Domain umstellbar auf
  „nur zugewiesene" (Playbooks/Resources der eigenen Persona) oder „aus".
- **Writes** (create/update/restore/link/transition fuer Persona/Playbook/
  Resource/Agent) standardmaessig **aus**, als Capability-Gruppen einschaltbar.
- **System-Prompt** listet nur die Tools, die der Agent wirklich darf
  (`tools-overview`-Platzhalter filtert pro Agent).
- **Serverseitige Durchsetzung** (User-Entscheid): Der API-Token wird optional an
  einen Agenten gebunden; das Backend setzt die Policy bei JEDEM Mutations-Endpoint
  durch und scoped die Read-Endpoints. MCP bleibt duenner Adapter (ADR-0030) und
  uebersetzt 403 → ToolError.

Hinweis: Ueber MCP gibt es kein Delete (ADR-0030) — „loeschen" ist daher kein
Tool und nicht Teil der Policy.

## Datenmodell (SSoT)

`packages/models/.../tool_policy.py` (neu):

- `ReadScope(StrEnum)`: `all` | `assigned` | `none`.
- `AgentCapability(StrEnum)`: `persona_write`, `playbook_write`, `resource_write`,
  `agent_write`, `promote_retire`.
- `AgentToolPolicy(BaseModel, extra=forbid)`:
  - Reads: `playbook_read: ReadScope=all`, `resource_read: ReadScope=all`,
    `persona_read: bool=True`, `agent_read: bool=True`.
  - Writes (default False): `persona_write`, `playbook_write`, `resource_write`,
    `agent_write`, `promote_retire`.
  - `allows(cap) -> bool` (write-Caps), Default-Instanz = Read-All/keine Writes.

`agent.py`: `tool_policy: AgentToolPolicy` zu `AgentCreate`/`AgentUpdate`(optional)/
`AgentRead`. `token.py`: `agent_id: UUID|None` zu `TokenCreate`/`TokenRead`/`TokenCreated`.

## Migration 0046

- `ALTER TABLE agent ADD COLUMN tool_policy jsonb NOT NULL DEFAULT '{}'::jsonb;`
- `ALTER TABLE api_token ADD COLUMN agent_id uuid REFERENCES agent(id) ON DELETE SET NULL;`
  (Single-Column-FK auf `agent.id`; Workspace-Konsistenz prueft der Token-Service.)

## Backend

- `agent_repository`: tool_policy in `_SELECT`/`_RETURNING`, insert/update (JSON).
- `agent_service`: tool_policy in create/update (Default-Policy).
- `token_repository`: `TokenAuthRow.agent_id`; insert/list/read/fetch_auth_by_hash.
- `token_service.create`: optionales `agent_id`, Agent-im-Workspace-Validierung.
- `core/security.py`:
  - `CurrentPrincipal.token_agent_id`, `WorkspaceContext.agent_id` + `tool_policy`.
  - `get_current_workspace` (Token-Pfad): laedt `agent.tool_policy`, fuellt ctx.
  - `require_capability(ctx, cap)`: no-op wenn `ctx.tool_policy is None`
    (Mensch/ungebunden), sonst 403 bei fehlender Cap.
- **Write-Gates**: in den Mutating-Services nach `require_role` ein
  `require_capability(...)` (Persona/Playbook/Resource/Agent + Link- + Transition-
  Services). Transition→active/inactive ⇒ `promote_retire`, sonst `*_write`.
- **Read-Scoping** (`core/agent_scope.py`, neu): recursive CTEs liefern
  `assigned_playbook_ids` (persona_playbook + playbook_composition-Closure) und
  `assigned_resource_ids` (playbook_resource_link der Playbooks + resource_composition-
  Closure). Services (playbook/resource list+fetch, triggers) wenden Scope an, wenn
  `ctx.tool_policy` gesetzt: `none`→403, `assigned`→restrict_ids, `all`→frei.
  `get_persona`/`fetch_agent` ueber `persona_read`/`agent_read` (on/off).
  Repo-list/fetch bekommen optionales `restrict_ids`.

## System-Prompt-Filter

- `RenderContext.tool_policy: AgentToolPolicy | None` (None = alles zeigen).
- `_TOOLS` um Write-Tools erweitern; jeder `_ToolDoc` traegt `capability`-Tag bzw.
  read-domain. `ToolsOverviewResolver` filtert nach Policy; bei `assigned` Read-Note.
- Agent-Render-Services laden `agent.tool_policy` (des **gerenderten** Agenten) in den
  RenderContext — wirkt auch im Web-Copy.

## MCP

- Keine Enforcement-Logik (serverseitig). 403-Uebersetzung in `client._raise_for_status`
  praezisieren („Dieser Agent darf dieses Tool nicht / sieht diese Ressource nicht").

## Frontend (apps/web)

- `api/types.ts`: `AgentToolPolicy`, `tool_policy` auf Agent; `agent_id` auf Token.
- `AgentEditorForm`: Sektion „Werkzeuge & Rechte" (Read-Scope-Selects + Write-Switches).
- `useAgentForm`: tool_policy in Defaults/Submit.
- Token-Erstellung: optionaler Agent-Select (Token an Agent binden).
- i18n (`agents`, `tokens`), Tests.

## DoD

- Python: `uv run ruff check . && uv run mypy . && uv run pytest -q`.
- Web: `npm run lint && npx tsc --noEmit && npm test && npm run build`.
- Tests: Write blocked/allowed, Read-Scope assigned/all/none, Token-Binding,
  System-Prompt-Filter.
