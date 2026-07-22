# Fix: zwei aktiv ausnutzbare HIGH-Befunde aus dem Tenancy-Security-Review

**Datum:** 2026-07-22 · **Branch:** `claude/autonomous-code-agent-setup-slz9qg`
**Auslöser:** 3-Paket-Security-Review der Mandanten-Isolation (security-reviewer,
parallel). Dieser Plan setzt die beiden aktiv ausnutzbaren HIGH-Befunde um.
Der dritte HIGH aus dem RLS-Coverage-Report (`api_token` ohne RLS-Policy) ist
laut Reviewer „aktuell kein aktiver Leak" (Defense-in-Depth) → separates
Follow-up, NICHT in diesem PR.

## Befund 1 (HIGH) — Agent-Tool-Policy bricht in der Cloud zusammen

**Fundstelle:** `apps/api/src/who2be_api/core/security.py:592`
(`_load_agent_tool_policy`-Aufruf), ausgeführt VOR `tenant_scope` (Zeile 644).

**Kern:** Der Read `SELECT tool_policy FROM agent WHERE id=$1 AND workspace_id=$2`
läuft ohne gesetzten `app.current_tenant`. Die Tabelle `agent` trägt STRIKTE RLS
(Migration 0037). Unter der Cloud-Rolle `who2be_app` (NOBYPASSRLS) liefert der
Read 0 Zeilen (fail-closed) → `tool_policy=None`. `tool_policy is None` heißt im
gesamten Code „keine Pro-Agent-Restriktion" → `require_capability`,
`*_read_restrict`, `require_write_rate`, `require_write_tags` werden No-Ops und
`require_memory_mode` wirft 403. Seit Migration 0048 ist JEDER aktive API-Token
agent-gebunden → in der Cloud ist die komplette Least-Privilege-Schicht für
MCP-Connectors wirkungslos. (Kein Cross-Tenant-Leak — Token-Pin + RLS greifen
nach Scope-Eintritt — aber vollständige Umgehung der Owner-definierten Grenzen.)

**Fix:** Den Policy-Read in einen kurzlebigen `tenant_scope(workspace_id, None)`
legen (org_id irrelevant: `agent` ist workspace-, nicht org-scoped). Analog zum
bereits korrekten Muster in `oauth_service._resolve_agent_membership`.

**Regressionstest (DB-frei):** `test_agent_policy_tenant_scope.py` — Fake-Pool
zeichnet `current_tenant_context()` zum Zeitpunkt des `agent`-Reads auf.
Vor Fix: `None` (Scope nicht betreten) → Test rot. Nach Fix: Tenant gesetzt →
grün. (Der echte RLS-Beweis läuft über `test_rls_isolation.py` unter
`who2be_app`; hier ohne DB skip-guarded.)

## Befund 2 (HIGH) — Cross-Agent-Leak über `GET /agents/{id}/render`

**Fundstelle:** `apps/api/src/who2be_api/routers/agents.py:147-154`
(`render_agent`). Der Schwester-Endpunkt `/rendered` (156-183) hat den
Self-Only-Guard („Security-Review MEDIUM-3"), `/render` nicht.

**Kern:** Jeder workspace-gebundene `w2b_`-Token (auch `assigned`-gescopte
Agent-Tokens) kann `GET .../agents/{fremde_id}/render` aufrufen und den voll
expandierten System-Prompt eines FREMDEN Agenten erhalten — gebaut mit dessen
`tool_policy`/`persona_id` → leakt Persona-/Playbook-/Resource-Inhalte außerhalb
des eigenen Read-Scopes.

**Fix:** `/render` exakt an `/rendered` angleichen: `agent_read_restrict(ctx)`
(sperrt `agent_read=none`) + Self-Only-Guard (`tool_policy is not None and
agent_id != ctx.agent_id` → 404). Menschen/JWT (`tool_policy is None`) behalten
die Workspace-weite UI-Sicht.

**Regressionstest (DB-frei):** in `test_render_scope_propagation.py` — fremd →
404, eigen → ok, Mensch → ok (spiegelt die vorhandenen `/rendered`-Tests).

## DoD

- [ ] Failing-Tests zuerst rot, nach Fix grün
- [ ] `uv run pytest apps/api/tests/test_render_scope_propagation.py apps/api/tests/test_agent_policy_tenant_scope.py`
- [ ] `uv run ruff check .` + `uv run ruff format .` + `uv run mypy apps/api`
- [ ] volle API-Test-Suite grün (keine Regression)
- [ ] Commit (Conventional) + Draft-PR mit Pointer auf diese Datei
