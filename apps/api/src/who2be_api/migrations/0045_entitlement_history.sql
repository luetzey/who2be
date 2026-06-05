-- Migration 0045 — entitlement_history (Compliance-Remediation WP-A, GoBD-Journal)
-- Plan: .claude/plan/2026-06-05-1311_compliance-de-saas-remediation.md
-- ADR: docs/adr/0031-compliance-audit-journals.md
--
-- Append-only Journal jedes Entitlement-Wechsels (Mollie/cloud/manual_override/
-- signed_license). Begleitet `org_entitlement` (Migration 0030/0043): die SSoT
-- bleibt der UPSERT-Stand, dieses Journal ist das lueckenlose Protokoll.
--
-- Aufbewahrung: `org_id` ist bewusst KEINE Foreign-Key-Referenz auf
-- `organization`. Der Org-Hard-Purge (`core/purge.py`, WP-D) loescht die Org-
-- Zeile via CASCADE der ganzen Hierarchie ab — das Journal soll diesen Schnitt
-- ueberleben (gesetzliche Aufbewahrungspflicht §14b UStG / §147 AO, geht der
-- DSGVO-Erasure vor; siehe ADR-0031 + WP-H/data-retention-and-erasure.md).
-- Ein FK mit ON DELETE NO ACTION wuerde den Purge blockieren; ein FK mit
-- ON DELETE CASCADE/SET NULL wuerde die Aufbewahrung brechen. Loesung: org_id
-- als reine UUID-Spalte fuehren — die Org-Zugehoerigkeit bleibt nachvollziehbar,
-- der Loeschpfad wird nicht durchbrochen.
--
-- Idempotenz: CREATE TABLE/INDEX via IF NOT EXISTS; RLS-Policy via
-- DROP IF EXISTS + CREATE; Grants idempotent.

CREATE TABLE IF NOT EXISTS entitlement_history (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- KEIN FK auf organization (Begruendung siehe Kommentar oben).
    org_id            uuid NOT NULL,
    status            text NOT NULL,
    features          jsonb NOT NULL DEFAULT '[]'::jsonb,
    expires_at        timestamptz,
    mcp_monthly_quota integer,
    mcp_rate_per_min  integer,
    grace_until       timestamptz,
    -- Herkunfts-Taxonomie analog org_entitlement (ADR-0028).
    source            text NOT NULL,
    external_ref      text,
    created_by        uuid,
    reason            text,
    recorded_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS entitlement_history_org_recorded_idx
    ON entitlement_history (org_id, recorded_at DESC);

-- Org-scoped RLS analog 0037_rls_policies.sql (PERMISSIV-bei-unset, weil der
-- Webhook-Schreibpfad keinen Org-Scope setzt — Begruendung siehe 0037).
ALTER TABLE entitlement_history ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON entitlement_history;
CREATE POLICY tenant_isolation ON entitlement_history
    USING (NULLIF(current_setting('app.current_org', true), '') IS NULL
           OR org_id = NULLIF(current_setting('app.current_org', true), '')::uuid)
    WITH CHECK (NULLIF(current_setting('app.current_org', true), '') IS NULL
           OR org_id = NULLIF(current_setting('app.current_org', true), '')::uuid);

-- Append-only-Grants fuer die App-Rolle. Bewusst NICHT in 0036 aufgenommen.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT SELECT, INSERT ON entitlement_history TO who2be_app;
    END IF;
END
$$;
