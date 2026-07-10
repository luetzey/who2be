# ADR-0042 — MCP `tools/list` pro Agent policy-gefiltert

- Status: Accepted
- Datum: 2026-07-10
- Kontext: ADR-0034 (MCP-HTTP-Transport, multi-tenant), ADR-0039
  (feinkörnige Agent-Schreibrechte + Read-Scopes), ADR-0040
  (System-Prompt-Authoring), Issue #304
- Plan: `.claude/plan/2026-07-10-1524_mcp-per-agent-tool-filtering.md`

## Kontext

Der MCP-Server registriert alle 47 Tools statisch auf einer `FastMCP`-Instanz.
Jeder verbundene Client sah bislang die komplette Liste, unabhängig von der
`AgentToolPolicy` seines Tokens — die Durchsetzung passiert erst beim Aufruf
serverseitig in der API (ADR-0039). Gleichzeitig ist die **beschreibende**
Tool-Liste im gerenderten System-Prompt (`tools-overview`-Placeholder,
`ToolsOverviewResolver`) bereits policy-gefiltert. Diskrepanz: Der Prompt sagt
„diese Tools sind gesperrt, versuche sie nicht", der MCP-Client bekommt sie
trotzdem angeboten. Zusatzproblem: Claude Chat budgetiert die
Connector-Tool-Payload hart (vgl. Fix 2026-07-07, `output_schema=None`,
230 KB → 65 KB) — 47 Tools sind für reine Konsum-Agenten unnötiger Ballast.

Zwei Sichtbarkeitslogiken existierten implizit: die kuratierte
`_ToolDoc.is_visible`-Semantik im API-Resolver und die (fehlende) Filterung im
MCP-Server. Ohne gemeinsame Quelle driften sie.

## Entscheidung

1. **SSoT-Mapping in `packages/models`**
   (`who2be_models/tool_requirements.py`): `MCP_TOOL_REQUIREMENTS` ordnet jedem
   der 47 MCP-Tool-Namen genau eine Sichtbarkeits-Anforderung zu — `always`
   (ping/whoami), `capabilities` (Write-Tools, Oder-Logik z. B. bei
   Transition-Tools: jeweilige `*_write` ODER `promote_retire`) oder
   `read_domain` (persona/playbook/resource/agent sowie `search` =
   Multi-Domain: sichtbar sobald ≥ 1 Inhalts-Domain lesbar; gilt auch für
   `find_usages`/`list_versions`/`get_version`/`diff_versions`).
   Zwei Prüffunktionen: `is_tool_visible(name, policy)` (Policy-basiert, für
   die API) und `is_tool_visible_for(name, ...)` (whoami-basiert, für den
   MCP-Adapter). Beide liefern `None` für unbekannte Namen — der Caller
   entscheidet fail-open.
2. **Per-Request-Filterung im MCP-Server** via FastMCP-Middleware
   (`PolicyFilterMiddleware`, `apps/mcp/src/who2be_mcp/policy_filter.py`):
   `on_list_tools` löst den Bearer des Requests per `whoami` auf (Cache pro
   Token-SHA-256, LRU ≤ 512, TTL 300 s — Muster `_workspace_cache`) und
   filtert die Tool-Liste mit `is_tool_visible_for`. `on_call_tool` lehnt
   Aufrufe ausgeblendeter Tools mit einer klaren `ToolError`-Meldung ab
   (statt API-403-Durchgriff). Statische FastMCP-Mechanismen
   (`enabled=False`, Tag-Filter) scheiden aus: Sie wirken global pro
   Server-Instanz, der HTTP-Transport ist aber multi-tenant (jeder Request
   trägt seinen eigenen Bearer, ADR-0034).
3. **API-Resolver konsumiert dieselbe SSoT:** `_ToolDoc` referenziert die
   konkreten Tool-Namen (`tool_names`) und delegiert `is_visible` als
   Gruppen-Oder an `is_tool_visible`. Paritätstests in beide Richtungen
   (API: jede Referenz existiert im Mapping, jedes Nicht-`always`-Tool ist
   gruppiert oder dokumentierte Ausnahme; MCP: registrierte Tools ==
   Mapping-Schlüssel) machen Drift zum CI-Fehler.
4. **Fail-open, keine Security-Grenze:** Schlägt die Policy-Auflösung fehl
   (kein Token, 401, Netz), liefert `tools/list` die ungefilterte Liste +
   Warn-Log und `on_call_tool` lässt durch. Begründung: Die Durchsetzung
   bleibt autoritativ bei der API (ADR-0039); ein leeres/fehlerhaftes
   `tools/list` reproduzierte das bekannte Symptom „verbunden, aber keine
   Tools". Die Filterung ist Kontext-Hygiene + Defense-in-Depth, sie ersetzt
   keine serverseitige Autorisierung.

## Sichtbarkeitsregeln (normativ)

- `ping`, `whoami`: immer sichtbar (auch ohne auflösbare Identity).
- Agent-gebundener Token (`unrestricted=False`): Read-Tools nach
  `read_scopes` (`none` blendet aus; fehlender Key fail-open sichtbar),
  Write-Tools nach Capability-Schnittmenge.
- `unrestricted=True` (Mensch/JWT, ungebundener Token): alles sichtbar;
  einzige Verfeinerung: Rolle `viewer` blendet Write-Tools aus.
- Unbekannter Tool-Name: sichtbar + Warn-Log; die Paritätstests verhindern,
  dass ein neues Tool ohne Mapping-Eintrag den CI passiert.

## Konsequenzen

- Ein Konsum-Agent mit Default-Policy sieht 21 statt 47 Tools; die
  `tools/list`-Payload schrumpft entsprechend (Claude-Chat-Budget).
- Prompt-Text (`tools-overview`) und echte Tool-Liste können nicht mehr
  widersprechen — beide hängen an `MCP_TOOL_REQUIREMENTS`.
- **Neues MCP-Tool ⇒ Pflicht-Eintrag im Mapping** (sonst Drift-Guard-Test
  rot) + Einsortierung in eine kuratierte `_TOOLS`-Gruppe oder die
  dokumentierte Ausnahmen-Liste des API-Paritätstests.
- Policy-Änderungen werden clientseitig nach Cache-TTL (≤ 300 s) bzw.
  Reconnect sichtbar; `notifications/tools/list_changed` ist bewusst nicht
  Teil dieser Iteration.
- stdio-Transport (Single-Tenant, statischer Env-Token) durchläuft dieselbe
  Middleware — identische Semantik, ein Code-Pfad.
