-- Migration 0037 — Row Level Security + tenant_isolation-Policies (Track I, §3.1)
-- Plan: .claude/plan/2026-06-02-1819_followups-rls-mollie-auth-fsl.md (R1/R2)
--
-- Zweite Verteidigungslinie hinter den App-`WHERE workspace_id`-Filtern. Jede
-- Connection des App-Pools traegt pro Request `app.current_tenant` (Workspace)
-- bzw. `app.current_org` (Org), gesetzt im Choke-Point core/tenancy.py.
--
-- ENABLE (nicht FORCE) ROW LEVEL SECURITY: der Tabellen-Owner (Migrations-/
-- On-Prem-Rolle) umgeht RLS weiterhin — nur `who2be_app` (NOBYPASSRLS) wird
-- gefiltert. Damit laufen On-Prem/Dev/Tests (Owner-Connection) unveraendert
-- (Plan R2: kein App-SQL-Unterschied).
--
-- current_setting(..., true) (missing_ok) ⇒ NULL statt Fehler, wenn die GUC
-- nie gesetzt wurde; NACH einem RESET (recycelte Pool-Connection) liefert sie
-- den Leerstring '' — daher ueberall NULLIF(..., '') vor dem ::uuid-Cast, sonst
-- wuerde '' den Cast sprengen. Beide Faelle (NULL/'' = "kein Mandant"):
--   * Workspace-Tabellen: STRIKT. Ohne Mandant matcht `workspace_id = NULL`
--     keine Zeile ⇒ fail-closed. In der Cloud setzt get_current_workspace die
--     GUC immer, bevor eine Workspace-Tabelle beruehrt wird.
--   * Org-Tabellen (org_entitlement, mcp_usage): PERMISSIV-bei-unset. Der
--     anonyme Billing-Webhook (POST /v1/billing/webhook, KEIN Workspace-Scope)
--     schreibt org_entitlement per explizitem org_id-PK ohne gesetzten
--     app.current_org — das ist KEIN Cross-Tenant-Read-Vektor. Lese-Zugriffe
--     laufen ausschliesslich workspace-scoped (app.current_org gesetzt ⇒
--     strikt). So bleibt der Webhook funktionsfaehig, ohne Billing-Code
--     anzufassen (Track-Abgrenzung), und Org-Daten-Reads bleiben isoliert.
--
-- Idempotenz: ENABLE RLS ist no-op bei bereits aktiv; Policy via DROP IF EXISTS
-- + CREATE. Schema-aware (unqualifiziert), repliziert im Isolations-Test.

-- Workspace-scoped: STRIKT auf app.current_tenant.
DO $$
DECLARE
    tname text;
BEGIN
    FOREACH tname IN ARRAY ARRAY[
        'persona',
        'persona_version',
        'playbook',
        'playbook_version',
        'persona_playbook',
        'resource',
        'resource_version',
        'playbook_resource_link',
        'system_prompt_template',
        'system_prompt_template_version',
        'agent',
        'playbook_composition',
        'resource_composition'
    ]
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

-- Org-scoped: PERMISSIV-bei-unset auf app.current_org (Begruendung oben).
DO $$
DECLARE
    tname text;
BEGIN
    FOREACH tname IN ARRAY ARRAY['org_entitlement', 'mcp_usage']
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tname);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', tname);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON %I '
            'USING (NULLIF(current_setting(%L, true), %L) IS NULL '
            '       OR org_id = NULLIF(current_setting(%L, true), %L)::uuid) '
            'WITH CHECK (NULLIF(current_setting(%L, true), %L) IS NULL '
            '       OR org_id = NULLIF(current_setting(%L, true), %L)::uuid)',
            tname,
            'app.current_org', '', 'app.current_org', '',
            'app.current_org', '', 'app.current_org', ''
        );
    END LOOP;
END
$$;
