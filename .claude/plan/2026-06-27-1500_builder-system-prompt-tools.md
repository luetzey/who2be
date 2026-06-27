# Builder-System-Prompt-Tools (Agent-Lifecycle vervollständigen)

Stand: 2026-06-27 · Branch `claude/charming-pasteur-pxz2l8`

## Status: UMGESETZT (2026-06-27)

Alle 6 Schichten + Tests + Security-Review erledigt. `security-reviewer`: keine
kritischen/hohen Befunde, Injection-Pfad doppelt gesperrt (`is_within` enthält
`system_prompt_write`); ein Low-Befund (fehlendes Capability-Label) behoben.
Verifikation: `ruff check .` clean, `mypy` auf allen geänderten Source-Dateien
clean (vorbestehende mypy-Fehler nur in fremden Test-Dateien), DB-freie Tests
grün (test_tool_policy 18, MCP-Suite 119, placeholder_renderer 98). DB-gebundene
Integrationstests brauchen Postgres (lokal nicht verfügbar; Service-Tightening
ist No-Op für ungebundene Tokens → Web unverändert). Web-UI-Toggle bewusst auf
Track 4 vertagt.

## Ziel (User-Request)

Der Builder-Agent soll System-Prompt-Templates über MCP **lesen, erstellen,
anpassen** können, damit er den gesamten Agent-Erstellungs-/Anpassungs-Workflow
fährt. **Entscheid (Option A):** Verfassen + zur Review einreichen ja —
**Aktivieren (→active) bleibt für Agent-Token gesperrt** (Injection-Schutz). Ein
Mensch/Admin promotet. Details: `docs/adr/0040-builder-system-prompt-authoring.md`.

## Ausgangsbefund (verifiziert, mit Quellen)

- REST-Endpunkte für Templates existieren vollständig
  (`apps/api/.../routers/system_prompts.py`: CRUD, versions, transition, restore,
  diff, provenance; Mount `/v1/workspaces/{ws}/system-prompts`).
- **Kein** MCP-Tool für Templates (`apps/mcp/...` grep leer).
- Agent-Token-Sperre sitzt NUR auf Transitionen
  (`version_status.py:147-155`, `actionable_by="none"`); create/update/restore
  sind heute nur `require_role(editor)` (kein Capability-Gate).
- Keine `system_prompt_write`-Capability im Modell (`tool_policy.py:47-60`).
- Builder-Policy (`workspace_repository.py:401-420`) hat alle `*_write` +
  `promote_retire`, aber nichts Template-bezogenes.
- `_TOOLS`-Register für die System-Prompt-Tools-Übersicht:
  `services/placeholders/resolvers/tools.py:99`.

## Umsetzung (schichtweise)

### 1. Modelle — `packages/models/.../tool_policy.py`
- `AgentCapability` um `system_prompt_write` ergänzen.
- `AgentToolPolicy.system_prompt_write: bool = False` (secure-by-default).
- `is_within`: Feld in `bool_fields` aufnehmen (Anti-Escalation).
- `granted_capabilities` zieht es automatisch (Enum-Iteration).

### 2. API-Gate — `services/version_status.py`
- `_require_transition_capability`: Sonderzweig für `entity_type ==
  "system_prompt_template"`:
  - `to_status ∈ {active, inactive}` → weiterhin hart `actionable_by="none"`
    (Agenten aktivieren/retiren NIE den eigenen System-Prompt).
  - sonst (draft/review) → `require_capability(system_prompt_write)`.
- Der generische `entity_type not in _WRITE_CAPABILITY`-Zweig bleibt als
  Safety-Net für sonstige Nicht-MCP-Entities.

### 3. Service-Gate — `services/system_prompt_template_service.py`
- `create`/`update`/`restore`: nach `require_role(editor)` ein
  `require_capability(ctx, AgentCapability.system_prompt_write)` (No-Op für
  ungebundene Tokens → Web-UI unverändert; tightening nur für Agent-Token,
  secure-by-default).
- Imports: `require_capability`, `AgentCapability`.

### 4. Builder-Seed + Backfill
- `workspace_repository._builder_tool_policy`: `system_prompt_write=True`.
- Migration `0052_builder_system_prompt_write.sql` (Muster wie 0051):
  `jsonb_set(tool_policy, '{system_prompt_write}', 'true')` für
  `agent` mit Template-`slug='agent-builder'`. Idempotent.

### 5. MCP — `apps/mcp/.../client.py` + `server.py`
- Reads: `list_system_prompts()`, `get_system_prompt(id)`. Versions/Diff über
  die Track-1-Tools: `EntityType`/`_ENTITY_PLURAL`/`_VERSION_MODEL` um
  `system_prompt → system-prompts → SystemPromptTemplateVersionRead` erweitern
  (`list_versions`/`get_version`/`diff_versions` decken Templates damit mit ab;
  `find_usages` bleibt unberührt — Templates haben keinen Usage-Endpunkt).
- Writes: `create_system_prompt`, `update_system_prompt`, `restore_system_prompt`,
  `transition_system_prompt` (Transition→active/inactive bleibt API-seitig für
  Agent-Token gesperrt; Tool reicht den 403 als klaren ToolError durch).

### 6. Tools-Übersicht — `services/placeholders/resolvers/tools.py`
- Neue `_ToolDoc`-Einträge (Reads + Writes), `capabilities=(system_prompt_write,)`
  → erscheinen im System-Prompt nur, wenn die Policy die Capability gewährt.

### 7. Tests
- Models: `system_prompt_write` Default False, `is_within`, `granted_capabilities`.
- API: agent-Token darf create/update mit Cap (Draft), draft→review ok,
  →active 403 `actionable_by="none"`; ohne Cap 403; ungebundener Token unverändert.
- MCP: neue Tools gegen MockTransport (Pfade, Dispatch system_prompt-Versions).

## Bewusst NICHT in diesem Track (defer)
- **Web-UI-Toggle** für `system_prompt_write` im `AgentEditorForm` → Track 4
  (Policy-Editor). Der Builder bekommt die Cap per Seed/Backfill; das manuelle
  Schalten für beliebige Agenten kommt mit der feinkörnigen-Rechte-Schicht.
- Aktivierungs-Autonomie (Option B) — bewusst verworfen (Injection-Grenze).

## DoD
- Python: `uv run ruff check . && uv run mypy . && uv run pytest -q` (lokal,
  betroffene Pakete; volle Suite braucht DB).
- `security-reviewer`-Subagent über das geänderte Gate (Capability + die
  beibehaltene Aktivierungs-Sperre).
- STATE/DECISIONS pflegen.
