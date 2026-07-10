# Plan: MCP `tools/list` pro Agent policy-gefiltert (ADR-0042)

_Erstellt: 2026-07-10 15:24 · Branch: `claude/code-agent-setup-h3khxa` · Status: in Arbeit_

## Problem

Der MCP-Server (`apps/mcp`) registriert alle ~46 Tools statisch auf einer
`FastMCP`-Instanz — jeder verbundene Client sieht die komplette Liste,
unabhängig von der `AgentToolPolicy` seines Tokens. Die Durchsetzung passiert
erst beim Aufruf serverseitig in der API (ADR-0039). Gleichzeitig ist die
**beschreibende** Tool-Liste im gerenderten System-Prompt bereits
policy-gefiltert (`ToolsOverviewResolver`,
`apps/api/src/who2be_api/services/placeholders/resolvers/tools.py`). Es
entsteht eine Diskrepanz: Der Prompt sagt „diese Tools sind gesperrt, versuche
sie nicht", der Client bekommt sie trotzdem angeboten.

Zusatznutzen: Claude Chat budgetiert die Connector-Tool-Payload hart
(dokumentiert in `server.py:85-91`, Fix 2026-07-07: 230 KB → 65 KB). Ein
Konsum-Agent mit Default-Policy sieht nach der Filterung nur noch ~13 Tools —
die `tools/list`-Antwort schrumpft nochmals deutlich.

## Zielbild

1. `tools/list` liefert pro Request nur die Tools, die die Policy des
   Bearer-Tokens gewährt (Multi-Tenant: Filterung zwingend per-Request).
2. Ein geteiltes Tool-Name→Anforderung-Mapping in `packages/models` ist SSoT
   für MCP-Filterung UND den `tools-overview`-Prompt-Resolver — kein Drift.
3. **Keine Security-Grenze:** Die API-Durchsetzung bleibt autoritativ; die
   Filterung ist UX/Kontext-Hygiene + Defense-in-Depth. Direkt aufgerufene,
   ausgeblendete Tools lehnt zusätzlich eine `on_call_tool`-Sperre mit klarer
   Meldung ab (statt API-403).

## Design-Entscheidungen (Empfehlung aus Vorab-Analyse, vom Owner bestätigt)

- **Per-Request-Middleware** (FastMCP 3.4.2 `Middleware.on_list_tools` /
  `on_call_tool`, verifiziert gegen installierte Version) statt statischer
  Mechanismen (`enabled=False`, Tag-Filter) — die wirken global pro
  Server-Instanz und scheitern am Multi-Tenant-HTTP-Transport.
- **Policy-Quelle:** `whoami` (`GET .../whoami`) — liefert `unrestricted`,
  `capabilities`, `read_scopes`, `role` in einem Call. Gecacht pro
  Token-SHA-256 (LRU + TTL), Muster wie `_workspace_cache` in `server.py`.
- **Fail-open:** Schlägt die Policy-Auflösung beim Listen fehl → volle Liste +
  Warn-Log. Begründung: Durchsetzung liegt bei der API; ein leeres `tools/list`
  reproduziert das bekannte „verbunden, aber keine Tools"-Symptom.
- **Sichtbarkeitsregeln:**
  - `ping`, `whoami`: immer sichtbar (`always`).
  - Agent-gebunden (`unrestricted=False`): Read-Tools nach `read_scopes`
    (`none` blendet aus; `search` sichtbar sobald ≥1 Inhalts-Domain lesbar),
    Write-Tools nach `capabilities` (Oder-Logik bei Transition-Tools:
    jeweilige `*_write` ODER `promote_retire` — wie im Resolver).
  - `unrestricted=True` (Mensch/JWT, ungebundener Token): volle Liste;
    einzige Verfeinerung: Rolle `viewer` blendet Write-Tools aus (Rollen-Gate
    lehnt sie ohnehin ab).
  - Unbekannter Tool-Name (nicht im Mapping): sichtbar lassen + Warn-Log
    (fail-open); ein Paritätstest verhindert, dass das im CI durchrutscht.

## Arbeitspakete (datei-disjunkt, 1 Sub-Agent pro WP)

### WP-1 — Fundament: geteiltes Mapping in `packages/models` (blockiert WP-2/WP-3)

- **Neu** `packages/models/src/who2be_models/tool_requirements.py`:
  - `ToolRequirement` (Pydantic, frozen): `read_domain:
    Literal["persona","playbook","resource","agent","search"] | None`,
    `capabilities: tuple[AgentCapability, ...] = ()`, `always: bool = False`.
  - `MCP_TOOL_REQUIREMENTS: dict[str, ToolRequirement]` — ALLE 46 in
    `apps/mcp/.../server.py` registrierten Tool-Namen (Quelle: die
    `@with_tool_log("<name>")`-Namen). Zuordnung exakt nach der bestehenden
    `_ToolDoc`-Semantik in `resolvers/tools.py` (inkl. `list_system_prompts`/
    `get_system_prompt`/`list_placeholders` → `system_prompt_write`;
    `find_usages`/`list_versions`/`get_version`/`diff_versions` → read-Tools:
    sichtbar sobald ≥1 Inhalts-Domain lesbar, wie `search`;
    `report_problem` → `feedback_write`).
  - `is_tool_visible(name: str, policy: AgentToolPolicy | None) -> bool | None`
    — `None` für unbekannte Namen (Caller entscheidet fail-open); Policy
    `None` = nur Read-Tools (bestehendes Resolver-Verhalten).
  - Zweite Prüffunktion auf `whoami`-Basis:
    `is_tool_visible_for(name, *, unrestricted, role, capabilities,
    read_scopes) -> bool | None` (für den MCP-Adapter, der kein
    `AgentToolPolicy`-Objekt hat, sondern `WhoAmIRead`-Felder).
- Export in `who2be_models/__init__.py`.
- **Tests** (`packages/models/tests/test_tool_requirements.py`): Matrix
  Default-Policy / Voll-Policy / `none`-Scopes / unbekannter Name /
  unrestricted+viewer; Vollständigkeit der Enum-Capabilities im Mapping.
- **DoD:** `uv run pytest packages/models -q`, `ruff check`, `mypy` (Paket) grün.

### WP-2 — API-Resolver auf SSoT umstellen (nach WP-1, ∥ WP-3)

- `apps/api/src/who2be_api/services/placeholders/resolvers/tools.py`:
  `_ToolDoc` bekommt `tool_names: tuple[str, ...]` (die konkreten MCP-Tools
  der kuratierten Gruppe); `is_visible` delegiert an
  `is_tool_visible(name, policy)` aus `who2be_models` (sichtbar, sobald EIN
  Tool der Gruppe sichtbar) — kuratierte Signaturen/Beschreibungen bleiben.
- **Paritätstest API-seitig:** jedes `MCP_TOOL_REQUIREMENTS`-Tool außer
  `always`-Tools kommt in genau einer `_ToolDoc`-Gruppe vor (Drift-Guard in
  beide Richtungen).
- **DoD:** bestehende Resolver-/Render-Tests unverändert grün
  (`uv run pytest apps/api -q -k "tool or placeholder or render"` + volle
  API-Suite in der Konsolidierung), ruff, mypy.

### WP-3 — MCP-Middleware (nach WP-1, ∥ WP-2)

- **Neu** `apps/mcp/src/who2be_mcp/policy_filter.py`:
  - `_whoami_cache`: Token-SHA-256 → `(WhoAmIRead, expires_at)`, LRU ≤512,
    TTL 300 s (Muster `_workspace_cache`).
  - `PolicyFilterMiddleware(Middleware)`:
    - `on_list_tools`: Token wie `_request_token` (HTTP: Bearer-Header,
      stdio: `settings.api_token`); `whoami` via `ApiClient` auflösen
      (Cache); filtern mit `is_tool_visible_for`; JEDER Fehler (kein Token,
      401, Netz) → ungefilterte Liste + `logger.warning`.
    - `on_call_tool`: bei **erfolgreich aufgelöster** Policy und
      unsichtbarem Tool → `ToolError` („Tool '<name>' ist für diesen Agenten
      nicht freigeschaltet — siehe whoami."); bei Auflösungsfehler oder
      unbekanntem Namen durchlassen (API enforced).
- `server.py`: nur `mcp.add_middleware(PolicyFilterMiddleware())` + Import
  (minimal-invasiv, keine Kollision mit WP-2).
- **Tests** (`apps/mcp/tests/test_policy_filter.py`):
  - Filter-Matrix über in-memory FastMCP-Client mit gemocktem `whoami`:
    Default-Policy (~13 Tools: ping/whoami/Reads/Feedback), Voll-Policy
    (alle), `resource_read=none` (Resource-Tools weg), unrestricted+admin
    (alle), unrestricted+viewer (keine Writes).
  - **Paritätstest (Drift-Guard):** `await mcp.get_tools()` ⊆
    `MCP_TOOL_REQUIREMENTS ∪ {always}` — ein neues Tool ohne
    Mapping-Eintrag bricht den Test.
  - Fail-open-Test (whoami wirft → volle Liste), Call-Block-Test
    (gesperrtes Tool → ToolError mit klarer Meldung).
- **DoD:** `uv run pytest apps/mcp -q`, ruff, mypy grün.

### WP-4 — Konsolidierung + Doku (Orchestrator, nach WP-2+WP-3)

- Integrations-Lauf: `uv run pytest --cov --cov-fail-under=85`, `ruff check .`,
  `ruff format --check .`, `mypy .` über das Gesamt-Repo.
- **ADR-0042** `docs/adr/0042-mcp-per-agent-tool-filtering.md` (Accepted):
  Kontext, Entscheidung (per-Request-Middleware, SSoT-Mapping, fail-open,
  keine Security-Grenze), Konsequenzen.
- Repo-Memory: STATE.md (immer), DECISIONS.md (Design-Entscheidung),
  CLAUDE.md `apps/mcp`-Absatz um einen Satz ergänzt.
- PR (Draft) mit Change-Log + Pointer auf diese Plan-Datei; Issue schließen.

## Abhängigkeiten / Reihenfolge

```
WP-1 (models, sync) ──> WP-2 (api)  ──┐
                    └─> WP-3 (mcp)  ──┴─> WP-4 (Konsolidierung, PR)
```

Datei-Disjunktheit: WP-1 nur `packages/models`; WP-2 nur `apps/api`;
WP-3 nur `apps/mcp`. Kein WP editiert Dateien eines anderen.

## Risiken

- **FastMCP-`Tool`-Objekte im Hook:** `on_list_tools` liefert
  `Sequence[Tool]`; Name via `tool.name`. Verifiziert: Hook-Signatur in
  3.4.2 vorhanden. Restrisiko: `get_http_headers` im Middleware-Kontext —
  falls der Request-Context dort nicht gesetzt ist, greift der
  Fail-open-Pfad (Test deckt das).
- **Client-Caching von tools/list:** MCP-Clients cachen pro Session; eine
  Session gehört zu genau einem Bearer → konsistent. Policy-Änderung wird
  nach TTL (≤300 s) bzw. Reconnect sichtbar — akzeptiert, kein
  `list_changed`-Notification-Aufwand in dieser Iteration.
- **Coverage-Gate 85 %:** neue Module brauchen belastbare Tests (WP-1/WP-3
  bringen eigene Testdateien mit; Matrix deckt Zweige).
