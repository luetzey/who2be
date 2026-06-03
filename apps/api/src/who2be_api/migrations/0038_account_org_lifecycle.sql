-- Migration 0038 — Account-/Org-Lifecycle (Track O, Plan §3.2)
-- Plan: .claude/plan/2026-06-03-2200_account-lifecycle-gdpr.md
--
-- Soft-Delete mit 30-Tage-Grace fuer Organizations + eine eigene
-- `account_deletion`-Tabelle fuer die Selbst-Loeschung des Accounts. Es gibt
-- KEINE lokale User-Tabelle (Identitaet lebt in GoTrue `auth.users`), darum
-- traegt `account_deletion` den User-Schluessel direkt.
--
-- Loesch-Vertrag:
--   * `organization.deleted_at` markiert die Vormerkung, `purge_after` das
--     frueheste Hard-Purge-Datum (now + 30d). Bis dahin bleibt die Zeile
--     bestehen, wird aber aus den Reads (`/v1/me`, `/v1/organizations`) und dem
--     Workspace-Zugriff (get_current_workspace) ausgeblendet.
--   * Der Hard-Purge (`who2be-purge`) macht `DELETE FROM organization` — die
--     bestehenden ON-DELETE-CASCADE-FKs raeumen Workspaces, Entities,
--     Versionen, Entitlement + Usage atomar ab.
--
-- Idempotenz (Runner-Vertrag, core/migrations.py): ADD COLUMN / CREATE TABLE /
-- CREATE INDEX ueber IF NOT EXISTS; GRANT ist von Natur aus idempotent und via
-- pg_roles-Guard gegen ein fehlendes `who2be_app` (reines OSS/Owner-Setup)
-- abgesichert. Schema-aware (unqualifizierte Namen), repliziert im
-- Isolations-Test im eigenen Schema.

-- Organization: Soft-Delete-Marker + Purge-Termin.
ALTER TABLE organization ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
ALTER TABLE organization ADD COLUMN IF NOT EXISTS purge_after timestamptz;

-- Teil-Index fuer den Purge-Scan (nur vorgemerkte Orgs).
CREATE INDEX IF NOT EXISTS organization_purge_after_idx
    ON organization (purge_after) WHERE deleted_at IS NOT NULL;

-- Account-Loeschung: eine Zeile je vorgemerktem User. `purged_at` bleibt NULL,
-- bis der Hard-Purge-Job den Account (Personal-Org, Tokens, Memberships,
-- GoTrue-User) tatsaechlich abgeraeumt hat.
CREATE TABLE IF NOT EXISTS account_deletion (
    user_id      uuid PRIMARY KEY,
    requested_at timestamptz NOT NULL DEFAULT now(),
    purge_after  timestamptz NOT NULL,
    purged_at    timestamptz
);

-- Teil-Index fuer den Purge-Scan (nur offene Loeschungen).
CREATE INDEX IF NOT EXISTS account_deletion_pending_idx
    ON account_deletion (purge_after) WHERE purged_at IS NULL;

-- DML-Grant fuer die App-Rolle (Cloud, RLS-Haertung 0036). account_deletion ist
-- control-plane (kein Workspace-Schluessel) — wie organization/workspace KEIN
-- RLS, der Zugriff ist user-gescoped in der App-Query. Guard gegen ein
-- fehlendes `who2be_app` (On-Prem/Dev verbinden als Owner).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON account_deletion TO who2be_app;
    END IF;
END
$$;
