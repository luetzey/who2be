-- Migration 0073 — Agent-WorkArea: `work_area` + `work_area_grant` (ADR-0047)
-- Plan: .claude/plan/2026-08-13-1200_agent-workarea-knowledge-base.md
--
-- Arbeitsort der Agenten (unversioniert, bewusst NEBEN dem Resource-Aggregat —
-- Abgrenzung siehe ADR-0047): eine Area ist entweder 'private' (gehoert genau
-- einem Agenten, Auto-Anlage beim ersten Zugriff) oder 'shared' (workspace-
-- weit, Zugriff ueber Grants). Der Zeilen-CHECK koppelt Scope und Owner hart:
-- private hat IMMER einen `owner_agent_id`, shared NIE.
--
-- `work_area_grant` materialisiert Lese-/Schreibrechte pro (Area, Agent) —
-- auch fuer die private Area wird die Owner-Grant-Row materialisiert, damit
-- die Scope-Filter-SQL (`core/workarea_scope.py`) uniform bleibt
-- (Plan-Entscheidung 5). Grant-Vergabe ist Menschen vorbehalten (Service).
--
-- `retention_days` NULL = unbegrenzt aufbewahren; sonst Loeschfrist in Tagen
-- fuer den Purge-Lauf (`who2be-purge`-Erweiterung).
--
-- Idempotenz: CREATE via IF NOT EXISTS; Policy via DROP IF EXISTS + CREATE;
-- GRANT idempotent; pg_roles-Guard schuetzt On-Prem/Dev ohne who2be_app
-- (Muster aus 0066/0070).

CREATE TABLE IF NOT EXISTS work_area (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id   uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    -- private: genau ein Owner-Agent; shared: workspace-weit per Grant.
    scope          text NOT NULL CHECK (scope IN ('private', 'shared')),
    owner_agent_id uuid REFERENCES agent (id) ON DELETE CASCADE,
    name           text NOT NULL,
    -- NULL = unbegrenzt; sonst Aufbewahrungsfrist in Tagen (Purge-Lauf).
    retention_days integer CHECK (retention_days > 0),
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    -- Kopplung Scope <-> Owner: private <=> owner_agent_id gesetzt.
    CHECK ((scope = 'private') = (owner_agent_id IS NOT NULL))
);

-- Genau EINE private Area je (Workspace, Agent) — die Auto-Anlage beim ersten
-- Zugriff bleibt damit race-frei idempotent.
CREATE UNIQUE INDEX IF NOT EXISTS work_area_private_owner_uniq
    ON work_area (workspace_id, owner_agent_id) WHERE scope = 'private';

-- Shared Areas sind im Workspace namenseindeutig (Adressierung ueber den Namen).
CREATE UNIQUE INDEX IF NOT EXISTS work_area_shared_name_uniq
    ON work_area (workspace_id, name) WHERE scope = 'shared';

CREATE INDEX IF NOT EXISTS work_area_workspace_id_idx
    ON work_area (workspace_id);

CREATE TABLE IF NOT EXISTS work_area_grant (
    workspace_id uuid NOT NULL,
    area_id      uuid NOT NULL REFERENCES work_area (id) ON DELETE CASCADE,
    agent_id     uuid NOT NULL REFERENCES agent (id) ON DELETE CASCADE,
    level        text NOT NULL CHECK (level IN ('read', 'write')),
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (area_id, agent_id)
);

-- Scope-Aufloesung laeuft pro Agent (readable_area_ids/writable_area_ids).
CREATE INDEX IF NOT EXISTS work_area_grant_agent_id_idx
    ON work_area_grant (agent_id);

CREATE INDEX IF NOT EXISTS work_area_grant_workspace_id_idx
    ON work_area_grant (workspace_id);

-- RLS strikt auf app.current_tenant (Workspace-Isolation, Muster 0066/0070).
DO $$
DECLARE
    tname text;
BEGIN
    FOREACH tname IN ARRAY ARRAY['work_area', 'work_area_grant']
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

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON work_area, work_area_grant
            TO who2be_app;
    END IF;
END
$$;
