-- Migration 0061 — Repariert `tool_policy.agent_read` der managed Builder-Agenten
--
-- `AgentToolPolicy.agent_read` ist ein `ReadScope` (all/assigned/none), KEIN
-- bool. Die Backfill-Migrationen 0047 (Builder) und 0060 (Builder-Lite) schrieben
-- faelschlich den JSON-Boolean `true` in `agent_read`. Beim Deserialisieren via
-- `AgentToolPolicy` (`extra="forbid"`, `agent_read: ReadScope`) wirft das eine
-- ValidationError — jeder Read, der die Agent-Zeile zu `AgentRead` validiert
-- (`list_agents`, `get_agent`, `fetch_agent`), antwortet dann mit 500.
--
-- Der Python-Seed (`_builder_tool_policy()`) war stets korrekt (`ReadScope.all`),
-- daher trifft es nur ueber die Migration angelegte Agenten (z. B. Builder-Lite
-- in Bestands-Workspaces). Normalisiere `agent_read` auf "all" (voller Read-Scope
-- des Meta-Agenten). Idempotent: greift nur, solange der Wert ein Boolean ist.

UPDATE agent
SET tool_policy = jsonb_set(tool_policy, '{agent_read}', '"all"', true),
    updated_at = now()
WHERE name IN ('Builder', 'Builder-Lite')
  AND is_managed = true
  AND jsonb_typeof(tool_policy -> 'agent_read') = 'boolean';
