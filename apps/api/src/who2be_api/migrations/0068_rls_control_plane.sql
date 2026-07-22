-- Migration 0068 — RLS tenant_isolation fuer die Steuer-Tabellen (Security-Review)
-- Security-Follow-up aus dem Tenancy-Isolation-Review: Backstop-Policies fuer
-- Tabellen, die einen Mandanten-Schluessel tragen, aber bislang KEINE
-- tenant_isolation-Policy hatten (waehrend 0036 ihnen volles CRUD fuer
-- who2be_app gewaehrt). Defense-in-Depth — KEIN aktiver Leak (alle App-Pfade
-- filtern bereits auf workspace_id/org_id); diese Migration schliesst die
-- fehlende DB-Zweitlinie fuer den Fall eines kuenftigen Query-Bugs.
--
-- Betroffen: api_token (HIGH-1), workspace_member + org_member (MEDIUM-1),
-- oauth_authorization_code (MEDIUM-3), audit_log (INFO-1).
--
-- PERMISSIV-bei-unset (wie org_entitlement/mcp_usage in 0037, workspace_invitation
-- in 0050), NICHT strikt — zwingend, weil diese Tabellen im Auth-/Bootstrap-Pfad
-- VOR dem Betreten von tenant_scope gelesen/geschrieben werden:
--   * api_token: `fetch_auth_by_hash` + `touch_last_used` (resolve_principal)
--     laufen ohne app.current_tenant — jeder Login. Strikt ⇒ 0 Zeilen ⇒ Auth tot.
--   * workspace_member: der JWT-Membership-Check (get_current_workspace) laeuft
--     VOR dem Scope; Invitation-Accept fuegt ein Mitglied ohne Scope ein.
--   * org_member: die org-Endpunkte (/v1/organizations) betreten nie tenant_scope.
--   * oauth_authorization_code: der Token-Exchange (POST /oauth/token) laeuft
--     ohne Scope und findet den Code per single-use sha256-PK.
-- Mit unset ⇒ kein Filter (Bootstrap funktioniert); mit gesetztem Mandanten
-- (workspace-scoped Endpunkte unter get_current_workspace) ⇒ strikt.
--
-- ENABLE (nicht FORCE) ROW LEVEL SECURITY: Owner/On-Prem/Dev/Tests + der
-- Owner-Purge-Job (account_repository, eigene Owner-Connection) umgehen RLS
-- weiter; nur who2be_app (NOBYPASSRLS) wird gefiltert (konsistent mit 0037).
-- Idempotent: ENABLE no-op bei bereits aktiv; Policy via DROP IF EXISTS + CREATE.
-- Schema-aware (unqualifiziert ⇒ aktueller search_path, wie im Isolations-Test).

-- (1) Workspace-scoped, permissiv-bei-unset auf app.current_tenant.
DO $$
DECLARE
    tname text;
BEGIN
    FOREACH tname IN ARRAY ARRAY[
        'api_token',
        'workspace_member',
        'oauth_authorization_code'
    ]
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tname);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', tname);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON %I '
            'USING (NULLIF(current_setting(%L, true), %L) IS NULL '
            '       OR workspace_id = NULLIF(current_setting(%L, true), %L)::uuid) '
            'WITH CHECK (NULLIF(current_setting(%L, true), %L) IS NULL '
            '       OR workspace_id = NULLIF(current_setting(%L, true), %L)::uuid)',
            tname,
            'app.current_tenant', '', 'app.current_tenant', '',
            'app.current_tenant', '', 'app.current_tenant', ''
        );
    END LOOP;
END
$$;

-- (2) Org-scoped, permissiv-bei-unset auf app.current_org.
DO $$
BEGIN
    EXECUTE 'ALTER TABLE org_member ENABLE ROW LEVEL SECURITY';
    EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON org_member';
    EXECUTE format(
        'CREATE POLICY tenant_isolation ON org_member '
        'USING (NULLIF(current_setting(%L, true), %L) IS NULL '
        '       OR org_id = NULLIF(current_setting(%L, true), %L)::uuid) '
        'WITH CHECK (NULLIF(current_setting(%L, true), %L) IS NULL '
        '       OR org_id = NULLIF(current_setting(%L, true), %L)::uuid)',
        'app.current_org', '', 'app.current_org', '',
        'app.current_org', '', 'app.current_org', ''
    );
END
$$;

-- (3) audit_log: BEIDE Scope-Spalten (org_id, workspace_id) sind nullable —
-- Lifecycle-/System-Events entstehen ohne Workspace-Bezug (0044). Die Policy
-- muss daher NULL-Scope-Zeilen immer durchlassen (sonst brechen Audit-INSERTs
-- fuer solche Events), gaetet auf workspace_id (die feinere Grenze; die
-- sicherheitsrelevanten Events member.*/token.* tragen sie). Kein Lese-Pfad
-- existiert heute (append-only, nur SELECT+INSERT fuer who2be_app) — reine
-- Vorsorge fuer einen kuenftigen Audit-Viewer.
DO $$
BEGIN
    EXECUTE 'ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY';
    EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON audit_log';
    EXECUTE format(
        'CREATE POLICY tenant_isolation ON audit_log '
        'USING (NULLIF(current_setting(%L, true), %L) IS NULL '
        '       OR workspace_id IS NULL '
        '       OR workspace_id = NULLIF(current_setting(%L, true), %L)::uuid) '
        'WITH CHECK (NULLIF(current_setting(%L, true), %L) IS NULL '
        '       OR workspace_id IS NULL '
        '       OR workspace_id = NULLIF(current_setting(%L, true), %L)::uuid)',
        'app.current_tenant', '', 'app.current_tenant', '',
        'app.current_tenant', '', 'app.current_tenant', ''
    );
END
$$;

-- (4) GRANT-Haertung (Least-Privilege): who2be_app braucht auf diesen Tabellen
-- KEIN DELETE — alle Loeschungen laufen ausschliesslich ueber den Owner-Purge-Job
-- (account_repository.PgAccountPurgeRepository, eigene Owner-Connection). Analog
-- zum append-only-REVOKE fuer status_history (0044:27). api_token behaelt UPDATE
-- (revoke setzt revoked_at); org_entitlement/mcp_usage behalten INSERT/UPDATE
-- (Billing-Upsert). pg_roles-Guard schuetzt On-Prem/Dev ohne die Rolle.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        REVOKE DELETE ON api_token, org_entitlement, mcp_usage FROM who2be_app;
    END IF;
END
$$;
