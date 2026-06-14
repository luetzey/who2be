# Track F — Persona-Pills + Skills-Tabelle

**Branch:** `feat/persona-pills-skills-table` (von Integrations-Stand mit Welle 1 + D)
**Quelle:** `.claude/plan/2026-06-02-1349_feature-expansion-…` §3.4, §4 Track F
**Datum:** 2026-06-02

## Ziel
Persona bekommt den vollen Pill-Satz wie der System-Prompt (Slash-Refs
playbook/resource + `playbooks-catalog` [all|triggered] + `resources-catalog`
[all|tag]) im BlockNote-Body; Skills-Tabelle aus `PersonaVersionContent.skills`;
`get_persona` rendert die Katalog-Pills fetch-time gegen die aktiven
Playbooks/Resources des Workspace.

## Backend
1. **`ResourcesCatalogResolver`** (`services/placeholders/registry.py`):
   neuer Resolver `kind='resources-catalog'`, `target_id ∈ {"", "all", "<tag>"}`.
   Quelle: aktive Resources des Workspace (optional Tag-Filter, jsonb).
   Tabelle **Resource | Tags | Aufruf | Beschreibung** mit
   `fetch_resource("<id>")`. Kein Persona-Kontext nötig → nie Miss; leere Menge
   → Hinweistext. Registry-Eintrag ergänzen.
2. **`render_skills_table`** (registry.py): Markdown-Tabelle **Skill | Hinweis**
   aus `skills`-Liste. Wiederverwendet `_table_cell`.
3. **Persona-Render-Pfad** (`PersonaService.render` + `PersonaRenderResponse`):
   Profil-Body (`content.content.blocks`) durch `render_template_body`
   (`persona_id=persona.id`) → Pills expandieren; Skills-Tabelle anhängen.
   Router `GET /personas/{id}/rendered` (mit `enforce_mcp_read_limit`).
4. **MCP**: `get_persona` liefert zusätzlich `body_rendered` (neues Feld auf
   `PersonaWithPlaybooks`), via Client `get_persona_rendered`.

## Frontend
5. **Shared Pill-Schema** (`PlaceholderBlock.tsx`): Kind `resources-catalog`
   (Union, propSchema-values, KIND_META). `slashMenu.ts`: Custom-Item.
6. **`ResourcesCatalogScopePicker`** (all | nach Tag).
7. **`PersonaProfileEditor`** (analog `PlaybookBodyEditor`) mit
   `allowedKinds={playbook,resource,playbooks-catalog,resources-catalog}`;
   ersetzt `ResourceEditor` in `PersonaEditorForm`; reicht `personaId` an die
   Preview durch.
8. **`SystemPromptEditor`**: mountet `ResourcesCatalogScopePicker` mit (das
   geteilte Slash-Menü bietet das neue Kind nun an).
9. **`PersonaSkillsTable`** read-only in `PersonaDetailPage` (Agenten-Sicht).

## DoD
Python `ruff+mypy+pytest` grün; Web `lint+tsc+test+build` grün;
`security-reviewer` für MCP/Render-Pfad. Conventional Commits, Draft-PR → main.
