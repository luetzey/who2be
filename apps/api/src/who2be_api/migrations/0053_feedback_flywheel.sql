-- Migration 0053 — Usage-/Feedback-Flywheel (ADR-0038)
-- Plan: .claude/plan/2026-06-27-1100_ai-native-mcp-and-rights.md (Track 3)
--
-- Zwei append-only, workspace-scoped Telemetrie-Tabellen, mit denen konsumierende
-- Agenten zuruckmelden, WAS sie genutzt haben (`usage_event`) und WIE gut es war
-- (`agent_feedback`). Beide fliessen NIE in einen gerenderten System-Prompt
-- (kein Injection-Vektor, ADR-0038) — sie speisen nur Kurations-Aggregate.
--
-- `entity_type` ist polymorph (persona/playbook/resource), daher KEIN Composite-FK
-- auf die Ziel-Tabelle (wie `audit_log`, 0044) — die Workspace-Isolation traegt
-- `workspace_id` + RLS. `agent_id` ist nullable (Mensch/ungebundener Token).
--
-- Append-only: GRANT nur SELECT, INSERT an die Laufzeitrolle `who2be_app`
-- (kein UPDATE/DELETE) — der Owner (Purge/Migration) behaelt Vollzugriff fuer
-- DSGVO-Erasure. RLS strikt auf `app.current_tenant` (Muster 0037).
--
-- Idempotenz: CREATE TABLE/INDEX via IF NOT EXISTS; ENABLE RLS no-op bei aktiv;
-- Policy via DROP IF EXISTS + CREATE; GRANT idempotent; pg_roles-Guard schuetzt
-- On-Prem/Dev (Owner-only ohne `who2be_app`).

CREATE TABLE IF NOT EXISTS usage_event (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL,
    -- Akteur: agent-gebundener Token traegt agent_id; Mensch/ungebundener Token NULL.
    agent_id     uuid,
    actor_id     uuid,
    entity_type  text NOT NULL,
    entity_id    uuid NOT NULL,
    version      int,
    -- applied | skipped | error (NULL = unspezifiziert).
    outcome      text,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS usage_event_entity_idx
    ON usage_event (workspace_id, entity_type, entity_id, created_at DESC);

CREATE TABLE IF NOT EXISTS agent_feedback (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL,
    agent_id     uuid,
    actor_id     uuid,
    entity_type  text NOT NULL,
    entity_id    uuid NOT NULL,
    version      int,
    -- helpful | outdated | incorrect | unclear.
    signal       text NOT NULL,
    note         text,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS agent_feedback_entity_idx
    ON agent_feedback (workspace_id, entity_type, entity_id, created_at DESC);

-- RLS strikt auf app.current_tenant (Workspace-Isolation, Muster 0037).
DO $$
DECLARE
    tname text;
BEGIN
    FOREACH tname IN ARRAY ARRAY['usage_event', 'agent_feedback']
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tname);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', tname);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON %I '
            'USING (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid) '
            'WITH CHECK (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid)',
            tname, 'app.current_tenant', '', 'app.current_tenant', ''
        );
    END LOOP;
END
$$;

-- Append-only: nur SELECT + INSERT fuer die Laufzeitrolle (kein UPDATE/DELETE).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT SELECT, INSERT ON usage_event TO who2be_app;
        GRANT SELECT, INSERT ON agent_feedback TO who2be_app;
    END IF;
END
$$;
