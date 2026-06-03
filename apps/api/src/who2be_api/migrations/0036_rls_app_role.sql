-- Migration 0036 — App-Role `who2be_app` + Grants (Track I, Plan §3.1)
-- Plan: .claude/plan/2026-06-02-1819_followups-rls-mollie-auth-fsl.md (R1/R2)
--
-- Cloud-Defense-in-Depth: die App verbindet zur Laufzeit als nicht-
-- privilegierte Rolle `who2be_app` (NOSUPERUSER, NOBYPASSRLS) ueber
-- APP_DATABASE_URL. Migrationen laufen weiter als Owner ueber DATABASE_URL
-- (who2be-migrate) — der Owner umgeht RLS (kein FORCE ROW LEVEL SECURITY in
-- 0037), sodass On-Prem/Dev, die als Owner verbinden, unveraendert laufen
-- (Plan R2: kein App-SQL-Unterschied).
--
-- Das Passwort der Rolle setzt der Betreiber out-of-band (Secret-Manager:
-- `ALTER ROLE who2be_app WITH PASSWORD '...'`). Diese Migration legt nur die
-- Rolle + Grants an — kein Secret im Repo. LOGIN, damit die App verbinden kann.
--
-- Idempotenz: Rolle via pg_roles-Guard; GRANT ist von Natur aus idempotent.
-- Schema-aware (current_schema()), damit der Isolations-Test im eigenen Schema
-- dieselben Grants bekommt.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        CREATE ROLE who2be_app LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;

-- Schema-Zugriff (kein CREATE — die App legt keine Objekte an).
DO $$
BEGIN
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO who2be_app', current_schema());
END
$$;

-- DML auf alle App-Tabellen. Bewusst NICHT auf `schema_migrations` (nur Owner)
-- und nicht auf System-Tabellen. Reihenfolge folgt der Migrationshistorie.
GRANT SELECT, INSERT, UPDATE, DELETE ON
    api_token,
    persona,
    persona_version,
    playbook,
    playbook_version,
    persona_playbook,
    organization,
    org_member,
    workspace,
    workspace_member,
    status_history,
    resource,
    resource_version,
    playbook_resource_link,
    workspace_invitation,
    system_prompt_template,
    system_prompt_template_version,
    agent,
    playbook_composition,
    org_entitlement,
    mcp_usage,
    resource_composition
TO who2be_app;
