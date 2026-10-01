-- Migration 0092 — RLS fuer workspace, organization, status_history; mcp_usage strikt
-- ADR-0055 (Trennungskonzept), Restrisiken R3/R4. Plan:
-- .claude/plan/2026-10-01-0645_m1-rls-control-plane-tabellen.md
--
-- Defense-in-Depth wie 0068: die App filtert bereits auf workspace_id/org_id.
-- Diese Migration gibt den Stammdaten und dem Statusverlauf die zweite Linie,
-- die alle Inhaltstabellen seit 0037 haben.
--
-- (1) workspace / organization — permissiv nur, solange KEIN Mandant gesetzt ist.
--     Ohne Mandanten laufen die Control-Plane-Pfade, die den Mandanten erst
--     ermitteln oder anlegen: Workspace->Org-Aufloesung in
--     get_current_workspace, /v1/me samt Lazy-Seed, /v1/organizations,
--     Anlage eines Workspace in einer Org, DSGVO-Export-Uebersicht.
--     Ist ein Mandant gesetzt (workspace-scoped Endpunkte), gilt:
--       workspace:    id = Mandant ODER org_id = Org des Mandanten
--                     (der Last-Workspace-Schutz zaehlt die Workspaces der Org)
--       organization: id = Org des Mandanten
--     "Kein Mandant" heisst: BEIDE GUCs leer. Ein Pfad, der nur
--     app.current_tenant setzt (tenant_scope(ws, None)), bleibt damit strikt.
--
-- (2) status_history — neue Spalte workspace_id, strikt auf app.current_tenant.
--     * Backfill aus der Entity-Tabelle (entity_type = Tabellenname).
--     * BEFORE-INSERT-Trigger leitet den Wert IMMER aus der Entity ab — die
--       Repos bleiben unveraendert (Muster 0035), ein mitgegebener Wert wird
--       ueberschrieben. SECURITY INVOKER: unter who2be_app laeuft der Lookup
--       unter RLS; eine fremde Entity ist unsichtbar, workspace_id bleibt NULL
--       und WITH CHECK weist den Insert ab (fail-closed).
--     * FK auf workspace ON DELETE CASCADE: Workspace- und Org-Purge raeumen
--       den Statusverlauf mit ab (R4a).
--     * Bleibt nullable: Altzeilen, deren Entity vor dieser Migration geloescht
--       wurde, lassen sich keinem Workspace mehr zuordnen. Fuer who2be_app sind
--       sie unter der strikten Policy unsichtbar; der Owner sieht sie weiter.
--
-- (3) mcp_usage — strikt auf app.current_org (bisher permissiv-bei-unset, 0037).
--     Jeder Zugriff laeuft unter get_current_workspace (Org gesetzt); der Purge
--     laeuft als Owner.
--
-- oauth_client bleibt global (Client-Registry, nicht mandantengebunden).
--
-- ENABLE (nicht FORCE) ROW LEVEL SECURITY wie 0037/0068: Owner, Migrationen,
-- Purge-Job und On-Prem umgehen RLS weiter; gefiltert wird nur who2be_app.
-- Idempotent (Runner-Vertrag, core/migrations.py) und schema-aware
-- (unqualifizierte Namen, current_schema()), wie der Isolations-Test es braucht.

-- (1a) workspace -----------------------------------------------------------------
ALTER TABLE workspace ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON workspace;
CREATE POLICY tenant_isolation ON workspace
    USING (
        (NULLIF(current_setting('app.current_tenant', true), '') IS NULL
         AND NULLIF(current_setting('app.current_org', true), '') IS NULL)
        OR id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        OR org_id = NULLIF(current_setting('app.current_org', true), '')::uuid
    )
    WITH CHECK (
        (NULLIF(current_setting('app.current_tenant', true), '') IS NULL
         AND NULLIF(current_setting('app.current_org', true), '') IS NULL)
        OR id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        OR org_id = NULLIF(current_setting('app.current_org', true), '')::uuid
    );

-- (1b) organization --------------------------------------------------------------
ALTER TABLE organization ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON organization;
CREATE POLICY tenant_isolation ON organization
    USING (
        (NULLIF(current_setting('app.current_tenant', true), '') IS NULL
         AND NULLIF(current_setting('app.current_org', true), '') IS NULL)
        OR id = NULLIF(current_setting('app.current_org', true), '')::uuid
    )
    WITH CHECK (
        (NULLIF(current_setting('app.current_tenant', true), '') IS NULL
         AND NULLIF(current_setting('app.current_org', true), '') IS NULL)
        OR id = NULLIF(current_setting('app.current_org', true), '')::uuid
    );

-- (2) status_history -------------------------------------------------------------
ALTER TABLE status_history ADD COLUMN IF NOT EXISTS workspace_id uuid;

UPDATE status_history sh SET workspace_id = e.workspace_id
  FROM persona e
 WHERE sh.entity_type = 'persona' AND sh.entity_id = e.id AND sh.workspace_id IS NULL;
UPDATE status_history sh SET workspace_id = e.workspace_id
  FROM playbook e
 WHERE sh.entity_type = 'playbook' AND sh.entity_id = e.id AND sh.workspace_id IS NULL;
UPDATE status_history sh SET workspace_id = e.workspace_id
  FROM resource e
 WHERE sh.entity_type = 'resource' AND sh.entity_id = e.id AND sh.workspace_id IS NULL;
UPDATE status_history sh SET workspace_id = e.workspace_id
  FROM system_prompt_template e
 WHERE sh.entity_type = 'system_prompt_template' AND sh.entity_id = e.id
   AND sh.workspace_id IS NULL;
UPDATE status_history sh SET workspace_id = e.workspace_id
  FROM external_tool e
 WHERE sh.entity_type = 'external_tool' AND sh.entity_id = e.id AND sh.workspace_id IS NULL;

CREATE INDEX IF NOT EXISTS status_history_workspace_id_idx
    ON status_history (workspace_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE c.conname = 'status_history_workspace_id_fkey'
          AND t.relname = 'status_history'
          AND n.nspname = current_schema()
    ) THEN
        ALTER TABLE status_history
            ADD CONSTRAINT status_history_workspace_id_fkey
            FOREIGN KEY (workspace_id) REFERENCES workspace (id) ON DELETE CASCADE;
    END IF;
END
$$;

-- Statische Zweige statt dynamischem SQL: die erlaubten Typen stehen im
-- CHECK status_history_entity_type_check (0065); ein unbekannter Typ liefert
-- NULL und scheitert damit an der Policy.
CREATE OR REPLACE FUNCTION w2b_fill_status_history_workspace_id() RETURNS trigger
LANGUAGE plpgsql AS $fn$
BEGIN
    NEW.workspace_id := CASE NEW.entity_type
        WHEN 'persona' THEN
            (SELECT workspace_id FROM persona WHERE id = NEW.entity_id)
        WHEN 'playbook' THEN
            (SELECT workspace_id FROM playbook WHERE id = NEW.entity_id)
        WHEN 'resource' THEN
            (SELECT workspace_id FROM resource WHERE id = NEW.entity_id)
        WHEN 'system_prompt_template' THEN
            (SELECT workspace_id FROM system_prompt_template WHERE id = NEW.entity_id)
        WHEN 'external_tool' THEN
            (SELECT workspace_id FROM external_tool WHERE id = NEW.entity_id)
    END;
    RETURN NEW;
END;
$fn$;

DROP TRIGGER IF EXISTS status_history_fill_ws ON status_history;
CREATE TRIGGER status_history_fill_ws
    BEFORE INSERT ON status_history
    FOR EACH ROW EXECUTE FUNCTION w2b_fill_status_history_workspace_id();

ALTER TABLE status_history ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON status_history;
CREATE POLICY tenant_isolation ON status_history
    USING (workspace_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (workspace_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);

-- (3) mcp_usage strikt -----------------------------------------------------------
ALTER TABLE mcp_usage ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON mcp_usage;
CREATE POLICY tenant_isolation ON mcp_usage
    USING (org_id = NULLIF(current_setting('app.current_org', true), '')::uuid)
    WITH CHECK (org_id = NULLIF(current_setting('app.current_org', true), '')::uuid);
