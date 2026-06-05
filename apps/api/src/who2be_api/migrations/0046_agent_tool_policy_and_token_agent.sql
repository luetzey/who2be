-- Migration 0046 — Pro-Agent-MCP-Tool-Policy + Token-an-Agent-Bindung
--
-- Zwei zusammengehoerige Spalten fuer das Feature „pro Agent steuern, welche
-- MCP-Tools er nutzen darf":
--
-- 1. `agent.tool_policy` (jsonb): die strukturierte Policy (AgentToolPolicy).
--    Reads (`playbook_read`/`resource_read` als all|assigned|none,
--    `persona_read`/`agent_read` als bool) plus Write-Capability-Gruppen.
--    Default `'{}'` deserialisiert in Pydantic zur Default-Policy
--    (Read-All / keine Writes) — Bestands-Agenten erben dieses Verhalten
--    ohne Datenmigration.
--
-- 2. `api_token.agent_id` (uuid, nullable): bindet einen API-Token optional an
--    einen Agenten. Ist sie gesetzt, setzt das Backend die Tool-Policy dieses
--    Agenten bei jedem Aufruf des Tokens durch (Writes gated, Reads gescoped).
--    Single-Column-FK auf `agent.id` mit ON DELETE SET NULL: wird der Agent
--    geloescht, faellt der Token auf reines Rollen-Gate zurueck statt zu
--    brechen. Workspace-Konsistenz (Agent lebt im selben Workspace wie der
--    Token) prueft der Token-Service vor dem INSERT — `agent.id` ist global
--    eindeutig (PK), daher genuegt der Single-Column-FK fuer referentielle
--    Integritaet.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS ist ein No-Op bei erneutem Lauf; den
-- FK legen wir nur an, wenn er noch nicht existiert.

ALTER TABLE agent
    ADD COLUMN IF NOT EXISTS tool_policy jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE api_token
    ADD COLUMN IF NOT EXISTS agent_id uuid;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'api_token_agent_id_fkey'
    ) THEN
        ALTER TABLE api_token
            ADD CONSTRAINT api_token_agent_id_fkey
            FOREIGN KEY (agent_id) REFERENCES agent (id) ON DELETE SET NULL;
    END IF;
END $$;
