-- Migration 0044 — Append-only-Erzwingung + audit_log (Compliance-Remediation WP-A)
-- Plan: .claude/plan/2026-06-05-1311_compliance-de-saas-remediation.md
-- ADR: docs/adr/0031-compliance-audit-journals.md
--
-- Zwei Bausteine:
--   1. `status_history` wird gegen die Laufzeitrolle `who2be_app` (NOBYPASSRLS)
--      DB-seitig append-only. Der Owner (Migrations- und Purge-Job) behaelt
--      bewusst Vollzugriff — der DSGVO-Erasure-Purge muss `changed_by`
--      anonymisieren koennen (WP-D, siehe ADR-0031).
--   2. Generisches `audit_log` fuer sicherheitsrelevante Admin-Events
--      (member.role_changed, member.removed, token.issued/revoked,
--      invitation.issued/revoked, account.deletion_requested, org.soft_deleted).
--      Append-only via `GRANT SELECT, INSERT` (kein UPDATE/DELETE) — Owner
--      darf weiter alles (Erasure-Anonymisierung).
--
-- Idempotenz (Runner-Vertrag, core/migrations.py): REVOKE ist no-op, wenn das
-- Privileg nie gegeben war; CREATE TABLE/INDEX via IF NOT EXISTS; GRANT ist von
-- Natur aus idempotent. pg_roles-Guard schuetzt On-Prem/Dev (Owner-only ohne
-- `who2be_app`) vor dem REVOKE/GRANT.

-- (1) status_history: append-only fuer die Laufzeitrolle.
-- Owner behaelt RLS-Bypass + Vollzugriff (kein FORCE ROW LEVEL SECURITY auf der
-- Tabelle), damit der Owner-Purge `changed_by` anonymisieren kann (WP-D).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        REVOKE UPDATE, DELETE ON status_history FROM who2be_app;
    END IF;
END
$$;

-- (2) audit_log: generisches Admin-/Security-Event-Journal, idempotent.
CREATE TABLE IF NOT EXISTS audit_log (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Org-/Workspace-Scope optional: Account-/Org-Lifecycle-Events koennen
    -- ohne Workspace-Bezug entstehen; Org kann nach Hard-Purge fehlen.
    org_id       uuid,
    workspace_id uuid,
    -- Akteur kann nach DSGVO-Erasure auf Sentinel '000…0' anonymisiert werden
    -- (WP-D). nullable, falls System-/Webhook-Events ohne Akteur entstehen.
    actor_id     uuid,
    action       text NOT NULL,
    -- Freitext-Identifier des Ziels (z. B. user_id, token_id, invitation_id).
    target       text,
    detail       jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_log_org_created_idx
    ON audit_log (org_id, created_at DESC) WHERE org_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS audit_log_workspace_created_idx
    ON audit_log (workspace_id, created_at DESC) WHERE workspace_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS audit_log_action_created_idx
    ON audit_log (action, created_at DESC);

-- Append-only-Grants fuer die App-Rolle. Bewusst NICHT in 0036 aufgenommen —
-- 0036 vergibt UPDATE/DELETE auf saemtliche App-Tabellen; das wuerde den
-- Append-only-Vertrag genau dieser Tabelle brechen.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT SELECT, INSERT ON audit_log TO who2be_app;
    END IF;
END
$$;
