-- Migration 0051 — agent_read von Bool auf ReadScope (none/assigned/all)
--
-- `AgentToolPolicy.agent_read` war ein Bool (Default true), binaer durchgesetzt:
-- true => alle Agenten des Workspace sichtbar, false => Tool aus. Damit sah jeder
-- Agent mit Default-Policy die Metadaten ALLER anderen. Das Feld wird zu einem
-- abgestuften ReadScope (wie playbook_read/resource_read):
--   none     => Tool aus (403)
--   assigned => nur der EIGENE Agent (secure by default)
--   all      => ganzer Workspace (Verwalter, z. B. Builder)
--
-- Bestands-Policies (JSONB auf agent.tool_policy) konvertieren:
--   explizit true  -> "assigned"  (normale Agenten werden self-only)
--   explizit false -> "none"
-- Fehlt der Key (z. B. tool_policy = '{}'), ist nichts zu tun — das Pydantic-
-- Modell defaultet jetzt selbst auf "assigned".
--
-- Den geseedeten Builder (verlinktes System-Prompt-Template mit Slug
-- 'agent-builder') anschliessend auf "all" heben, damit er weiterhin alle
-- Agenten des Workspace sieht und verwalten kann.
--
-- Idempotent: die WHERE-Klauseln matchen nur den jeweiligen Alt-Zustand; ein
-- erneuter Lauf findet keine bool-Werte mehr.

-- 1) true -> "assigned"
UPDATE agent
SET tool_policy = jsonb_set(tool_policy, '{agent_read}', '"assigned"', true)
WHERE tool_policy -> 'agent_read' = 'true'::jsonb;

-- 2) false -> "none"
UPDATE agent
SET tool_policy = jsonb_set(tool_policy, '{agent_read}', '"none"', true)
WHERE tool_policy -> 'agent_read' = 'false'::jsonb;

-- 3) Builder -> "all" (laeuft NACH 1/2, ueberschreibt das self-Default)
UPDATE agent a
SET tool_policy = jsonb_set(a.tool_policy, '{agent_read}', '"all"', true)
FROM system_prompt_template t
WHERE a.system_prompt_template_id = t.id
  AND t.slug = 'agent-builder';
