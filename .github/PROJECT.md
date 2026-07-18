# PROJECT — Aktuelles Vorhaben

_Primäre Heimat für Outcome, Why, Acceptance Criteria, Constraints und
Out of Scope des jeweils aktiven Vorhabens. Pro Vorhaben gepflegt; Historie
liegt in `.claude/plan/` und `docs/adr/`._

## Vorhaben: Externe Tools (MCP-Server-Bindings) + `tool-ref`-Placeholder

Detail-Blueprint: `.claude/plan/2026-07-18-1315_external-tools-tool-ref.md`

### Outcome

Externe MCP-Server/Tools sind als versionierte Workspace-Objekte
(`external_tool`) mit stabilem Fähigkeits-Alias (z. B. `todo`) hinterlegt und
per `tool-ref`-Pill in Playbooks, Personas, Resources und
System-Prompt-Vorlagen referenzierbar. Ein Tool-Wechsel (z. B. Todoist →
Things 3) ist genau EIN Edit am Tool-Objekt; alle gerenderten Prompts tragen
ab dem nächsten Fetch die neue Bindung.

### Why

Tool-Anweisungen werden heute als Freitext dupliziert; ein Wechsel bedeutet
N Edits mit Drift-Risiko. Die Fetch-Time-Placeholder-Architektur liefert die
„einmal ändern, überall aktuell"-Semantik bereits — es fehlt die Ziel-Entität.

### Acceptance Criteria

1. CRUD + Status-Workflow (draft→review→active→inactive) + Versionierung für
   `external_tool` per REST und Web-UI; Alias pro Workspace eindeutig (409).
2. `tool-ref`-Pill (target_id = Alias) ist in allen 4 Editoren einfügbar und
   expandiert beim Agent-Rendering zur aktiven Bindung; ohne aktives Tool →
   sauberer Miss (`unresolved_key`), kein Crash.
3. Bindungswechsel per Edit + Promote wird ohne Änderung an referenzierenden
   Inhalten beim nächsten Fetch wirksam (Test belegt Ende-zu-Ende).
4. MCP: `list_external_tools`/`get_external_tool` (read) + Builder-Writes
   capability-gated; Einträge in `MCP_TOOL_REQUIREMENTS` (Drift-Guards grün);
   `search` findet externe Tools.
5. Policy: Read-Scope-Domain `external_tool` + Capability
   `external_tool_write` inkl. `is_within`-Anti-Escalation und Policy-UI.
6. DSGVO-Purge + Einzel-Export decken die neuen Tabellen ab.
7. DoD beider Stacks grün (pytest ≥85 % Coverage, ruff, mypy strict; Web
   lint/tsc/test:coverage ≥79 % Branches/build) — lokal = CI.

### Constraints

- Rein beschreibende Daten: KEINE Server-URLs, KEINE Credentials/Secrets.
- Bestehende Muster wiederverwenden (versioned_repository, Placeholder-
  Registry, ListFilterBar/StatusBadge, shadcn-Primitives, Token-Design).
- Additiv: keine Breaking Changes an bestehenden APIs/Policies
  (JSONB-abwärtskompatible Policy-Erweiterung).
- Arbeit über Branch + Pull Request, Conventional Commits.

### Out of Scope

- MCP-Gateway/Proxy (Who2Be routet keine Tool-Calls) — dokumentierter
  späterer Ausbaupfad im ADR.
- Credential-Store, Runtime-Verbindungsprüfung, Dashboard-KPIs,
  Editionen-Gating, Builder-Playbook-Erweiterung (v1.1-Kandidaten).
