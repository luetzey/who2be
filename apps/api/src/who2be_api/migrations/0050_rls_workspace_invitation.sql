-- Migration 0050 — RLS tenant_isolation fuer workspace_invitation
-- Security-Follow-up INFO-1 aus dem MCP/Tenant-Isolation-Audit (vgl. PR #235/#236).
-- Defense-in-Depth — KEIN aktiver Leak (die App filtert bereits auf workspace_id).
--
-- workspace_invitation traegt workspace_id, war aber nicht in der 0037-Liste:
-- die Admin-Pfade (create/list/revoke) verliessen sich allein auf den App-
-- `WHERE workspace_id`-Filter ohne RLS-Zweitlinie. Diese Migration schliesst die
-- Luecke.
--
-- PERMISSIV-bei-unset (wie org_entitlement/mcp_usage in 0037), NICHT strikt:
-- der Invitation-Accept-Pfad (POST /v1/invitations/{token}/accept — top-level,
-- anonym authentifiziert) laeuft OHNE gesetzten app.current_tenant, denn der
-- akzeptierende User ist noch kein Workspace-Member. Eine strikte Policy wuerde
-- den (single-use, sha256-token-gegateten) Lookup auf 0 Zeilen filtern und das
-- Onboarding brechen. Mit unset ⇒ kein Filter (Accept funktioniert); mit
-- gesetztem Tenant (Admin-Pfade unter get_current_workspace) ⇒ strikt. Der
-- token_hash ist UNIQUE + hochentropisch — der unscoped Accept-Pfad ist daher
-- kein Cross-Tenant-Read-Vektor.
--
-- BEWUSST AUSGENOMMEN: status_history (vom Audit ebenfalls genannt) hat KEINE
-- workspace_id (0012) — eine workspace_id-Policy ist dort nicht anwendbar. Die
-- Isolation laeuft ueber den Join zur (RLS-geschuetzten) Entity, siehe
-- dashboard_repository. Kein Handlungsbedarf.
--
-- ENABLE (nicht FORCE) ROW LEVEL SECURITY: Owner/On-Prem/Dev/Tests umgehen RLS
-- weiter; nur who2be_app (NOBYPASSRLS) wird gefiltert (konsistent mit 0037).
-- Idempotent: ENABLE no-op bei bereits aktiv; Policy via DROP IF EXISTS +
-- CREATE. Schema-aware (unqualifiziert ⇒ aktueller search_path, wie im
-- Isolations-Test).

ALTER TABLE workspace_invitation ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON workspace_invitation;
CREATE POLICY tenant_isolation ON workspace_invitation
    USING (
        NULLIF(current_setting('app.current_tenant', true), '') IS NULL
        OR workspace_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    )
    WITH CHECK (
        NULLIF(current_setting('app.current_tenant', true), '') IS NULL
        OR workspace_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
    );
