# Externe Tools (MCP-Server-Bindings) + `tool-ref`-Placeholder

_Blueprint 2026-07-18 · Status: Entwurf, wartet auf Freigabe (Issues/Umsetzung)_
_Playbook: Projekt-Blueprint · Entscheidungs-Weichen mit Owner am 2026-07-18 gestellt_

## Outcome

Workspace-Mitglieder können externe MCP-Server/Tools (z. B. Todoist, Things 3,
Kalender) **einmal zentral** als versioniertes Objekt hinterlegen und in
Playbooks, Personas, Resources und System-Prompt-Vorlagen über einen stabilen
**Fähigkeits-Alias** (z. B. `todo`) referenzieren. Ändert sich das konkrete
Tool (Todoist → Things 3), wird **nur das eine Objekt** aktualisiert — alle
gerenderten Agent-Prompts tragen ab dem nächsten Fetch automatisch die neue
Bindung (Fetch-Time-Expansion, kein Re-Edit der referenzierenden Inhalte).

## Why

Heute gibt es keinen Ort für „welches externe Tool erfüllt Fähigkeit X".
Tool-Anweisungen werden als Freitext in Playbooks/Personas dupliziert; ein
Tool-Wechsel bedeutet N Edits mit Drift-Risiko. Die bestehende
Placeholder-Architektur (ADR-0025/0040, Fetch-Time-Rendering) liefert die
„einmal ändern, überall aktuell"-Semantik bereits — es fehlt nur die
Ziel-Entität und ein Resolver.

## Entscheidungen (Owner, 2026-07-18)

1. **Ausbaustufe B:** eigenes versioniertes Aggregat + Placeholder-Kind
   `tool-ref`. Rein **instruktive** Bindung (Prompt-Anweisung); ein echter
   MCP-Gateway/Proxy (Ausbaustufe C) ist explizit NICHT Teil dieses Features,
   wird aber im ADR als mögliche spätere Ausbaustufe festgehalten (der Alias
   wird dann zum Proxy-Namespace).
2. **Datentiefe: nur beschreibend.** Name, Server-Bezeichnung, Tool-Namen,
   Nutzungshinweise. KEINE Server-URLs, KEINE Credentials → minimale
   Security-Oberfläche, kein neuer Secret-Store.
3. **Einsatzorte: überall.** Alle Body-Rendering-Pfade (System-Prompt-Vorlagen,
   Persona-, Playbook-, Resource-Bodies).
4. **Alias als Referenz.** Pills referenzieren den Fähigkeits-Alias (`todo`),
   nicht die Tool-UUID. Re-Binding bricht keine Referenzen; auch ein komplett
   neues Tool-Objekt kann den Alias übernehmen.

### Naming (entschieden, Alternativen dokumentiert)

Entität heißt im Code/DB **`external_tool`** („Externe Tools" in der UI).
Verworfen: `tool` (kollidiert mit MCP-Protokoll-„tools" und
`tool_policy`/`tool_requirements`), `capability` (kollidiert mit
`AgentCapability`), `integration` (zu generisch, kollidiert mit
`who2be_api/integrations/` = interne GoTrue-Adapter).
Placeholder-Kind heißt **`tool-ref`** (kurz, editor-freundlich).

## Architektur

Modularer Monolith, bestehende Schichten (ADR-0002): Router → Service →
Repository; geteilte Models in `packages/models`. Das Aggregat folgt exakt dem
Persona/Resource-Muster (`versioned_repository`, Status-Workflow
draft→review→active→inactive, RLS, Workspace-Scope).

```mermaid
graph TB
  subgraph packages/models
    ETM[external_tool.py<br/>ExternalToolContent/Read/Create/Update]
    TR[tool_requirements.py<br/>+ Mapping neue MCP-Tools]
    TP[tool_policy.py<br/>+ read_scope 'external_tool',<br/>+ capability external_tool_write]
  end
  subgraph apps/api
    MIG[migrations/0065_external_tool.sql<br/>Tabellen + RLS + Alias-Unique]
    REPO[external_tool_repository.py<br/>via versioned_repository]
    SVC[external_tool_service.py]
    RTR[routers/external_tools.py<br/>CRUD + Transition + Export]
    RES[placeholders/resolvers/tool_ref.py<br/>ToolRefResolver: alias → aktive Bindung]
    REG[placeholders/registry.py<br/>REGISTRY['tool-ref']]
    CAT[kind_catalog.py + list_placeholders]
  end
  subgraph apps/mcp
    MCPT[Tools: list_external_tools,<br/>get_external_tool + Builder-Writes]
  end
  subgraph apps/web
    FEAT[features/tools<br/>Liste + Detail]
    PICK[editor: ToolPicker + tool-ref-Pill<br/>in allen 4 Editoren]
  end
  ETM --> REPO --> SVC --> RTR
  MIG --> REPO
  SVC --> RES --> REG --> CAT
  TP --> RTR
  TR --> MCPT --> SVC
  FEAT --> RTR
  PICK --> CAT
```

### Datenmodell

- `external_tool` (Aggregat-Zeile): `id`, `workspace_id`, `owner_id`,
  **`alias`** (Slug-Format wie `resource_slug`/0064; partieller
  UNIQUE-Index `(workspace_id, alias)`), `is_managed=false`,
  Timestamps. Alias lebt auf der Aggregat-Zeile (stabile Identität über
  Versionen hinweg), analog Template-Slug.
- `external_tool_version`: Standard-Versionsspalten + `content` (JSONB):
  - `display_name` — „Todoist"
  - `mcp_server_name` — Anzeigename des Connectors in der Runtime („Todoist MCP")
  - `tool_names: list[str]` — relevante Tool-Bezeichner (`add_task`, …)
  - `usage_notes` — BlockNote-Body (wann/wie nutzen; Do/Don't)
  - `fallback_note: str | None` — optionaler Hinweis, was der Agent tun soll,
    wenn der Server in der Runtime nicht verbunden ist
  - `tags: list[str]`
- RLS + Grants wie persona/resource (SELECT/INSERT/UPDATE/DELETE für
  `who2be_app`, workspace-Klausel).

### Rendering-Vertrag (`tool-ref`)

Pill im BlockNote-Body: `{"type":"placeholder","props":{"kind":"tool-ref",
"target_id":"todo","label":"Tool: To-do-Liste"}}`. Der `ToolRefResolver`
sucht die **aktive** Version des Tools mit `alias='todo'` im Workspace und
expandiert zu einem kompakten Anweisungsblock:

> **Fähigkeit „todo" → Todoist.** Nutze den MCP-Server „Todoist MCP"
> (Tools: `add_task`, `list_tasks`). Hinweise: … Fallback: …

Kein aktives Tool zum Alias → Miss (`unresolved_key`, Verhalten wie
`playbook`/`resource`-Resolver). Read-Scope-Filterung analog bestehender
Resolver (neue Domain `external_tool` in `read_scopes`; `none` → Miss).

## Modul-Spezifikation (Dateien je WP, disjunkt)

**WP-1 Backend-Fundament** (`packages/models/src/who2be_models/external_tool.py`,
`__init__.py`-Exporte, `apps/api/.../migrations/0065_external_tool.sql`,
`repositories/external_tool_repository.py`, `services/external_tool_service.py`,
`routers/external_tools.py` + Router-Registrierung, `routers/_export.py`,
GDPR-Purge, OpenAPI-Golden): CRUD + Status-Transitions + Einzel-Export nach dem
Resource-Muster; Alias-Validierung (Slug) + 409 bei Alias-Kollision;
Quota-Hook (`entity_quota_service`).

**WP-2 Rendering** (`services/placeholders/resolvers/tool_ref.py`,
`resolvers/__init__.py`, `registry.py`, `kind_catalog.py`,
`placeholder_preview_service.py`, `_core.py` nur falls `blocks_plain_text`
Anpassung braucht): Resolver + Registry + Katalog-Eintrag + Preview; greift
automatisch in allen Body-Rendering-Pfaden (Templates + Persona/Playbook/
Resource `body_rendered`).

**WP-3 Policy + MCP** (`packages/models/.../tool_policy.py`,
`tool_requirements.py`, `whoami.py`; `apps/mcp/...` Tool-Registrierungen +
Client): Read-Scope-Domain `external_tool` (Default `all`, JSONB-kompatibel)
+ Capability `external_tool_write` (Default aus); MCP-Tools
`list_external_tools`, `get_external_tool(alias)` (read) sowie
`create/update/transition/restore_external_tool` (Builder, capability-gated).
**Pflicht:** Mapping-Einträge in `MCP_TOOL_REQUIREMENTS` (ADR-0042,
Drift-Guard-Tests schlagen sonst rot). `search` (ADR-0037) um Typ
`external_tool` erweitern.

**WP-4 Web-Verwaltung** (`apps/web/src/features/tools/**`, Nav/Routing,
`api/client.ts` additiv, i18n de/en): Liste (ListFilterBar/StatusBadge-Muster)
+ Detail (Formularfelder + usage_notes-Editor, ReviewBanner/Status-Aktionen,
`VersionHistory`, FeedbackPanel, ManagedNotice-kompatibel, Danger-Zone).

**WP-5 Editor-Pills** (`components/editor/**`: neuer `ToolPicker`,
Pill-Render/Preview; Einbindung in System-Prompt-Editor + die
BlockNote-Editoren von Persona/Playbook/Resource): Pill einfügbar + Vorschau
(`usePlaceholderPreview`). Kein Save-Sync-Link nötig (Alias-Referenz erzeugt
keine Row-Links) — bewusster Unterschied zu `playbook_body_pills.py`;
Reverse-Lookup („Verwendet in") V1 über `find_usages`-Erweiterung ODER
Body-Scan, Entscheidung im WP (Drei-Optionen-Check, falls unklar).

**WP-6 Doku + Kontext** (`docs/adr/0043-external-tool-bindings.md`,
`docs/agent-axes.md`-Querverweis, `CLAUDE.md`-Strukturzeile,
`.claude/context/STATE.md`/`DECISIONS.md`, `.github/PROJECT.md`-Pflege):
ADR (Kontext, Entscheidung B, Alternativen A/C, Ausbaupfad Gateway),
Kontext-Pflege.

## Test-Plan (Pyramide, ADR-0041)

- **Unit (models):** Alias-Slug-Validierung, Content-Roundtrip,
  Policy-`is_within`-Anti-Escalation mit neuer Domain/Capability.
- **Integration (API, Wegwerf-Postgres):** CRUD/Transition/Export/Quota,
  Alias-Unique 409, RLS/Workspace-Isolation (404 fremder Workspace),
  Resolver Hit/Miss/read_scope-none, Preview-Endpoint, Renderer über alle 4
  Body-Pfade, GDPR-Purge deckt neue Tabellen.
- **MCP (Contract):** neue Tools inkl. capability-Gates + REST↔MCP-Parität
  (`contract`-Marker); Drift-Guards Registry↔`MCP_TOOL_REQUIREMENTS` grün.
- **Web (Vitest):** Liste/Filter, Detail-Form + Statusfluss, ToolPicker,
  Pill-Preview, A11y-Checks der neuen Seiten.
- **Gates:** `uv run pytest --cov --cov-fail-under=85`, ruff, mypy strict;
  Web lint/tsc/`test:coverage` (Branches-Floor 79)/build — lokal = CI.

## Roadmap / Wellen

Milestone **„Externe Tools v1"**, 6 Issues (= WP-1…6).
Welle 1: WP-1 → danach parallel Welle 2: WP-2 + WP-4 (datei-disjunkt) →
Welle 3: WP-3 + WP-5 → Welle 4: WP-6 + Konsolidierung (Integrations-Tests,
Standards-Check, DoD-Nachweis).

## Out of Scope (v1)

- MCP-Gateway/Proxy (Ausbaustufe C), Credentials-/URL-Speicherung,
  Runtime-Verbindungsprüfung („ist der Server wirklich verbunden?").
- Dashboard-KPIs für Tools, Editionen-Gating, Builder-Playbook-Erweiterung
  (Builder lernt `tool-ref` kennen) — Kandidaten für v1.1.

## Offene Punkte

- WP-5: Mechanik „Verwendet in" (find_usages vs. Body-Scan) — Entscheidung
  im WP mit Drei-Optionen-Check, falls nicht eindeutig.
- Seed-Beispiel (Demo-Tool im Onboarding-Seed)? Default: nein.
