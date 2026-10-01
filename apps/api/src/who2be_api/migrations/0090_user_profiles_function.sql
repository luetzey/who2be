-- Migration 0090 — Nutzerprofile nur ueber `w2b_user_profiles(uuid[])`
-- Plan: .claude/plan/2026-10-01-0230_n1a-user-profiles-security-definer.md
--
-- E-Mail und `raw_user_meta_data` leben im GoTrue-Schema `auth.users`. Die
-- Laufzeitrolle `who2be_app` (0036) bekommt darauf bewusst KEINEN Zugriff:
-- `auth.users` traegt kein RLS, ein Grant machte jedes Profil fuer jeden
-- Mandanten lesbar. Stattdessen liefert diese SECURITY-DEFINER-Funktion
-- `id, email, raw_user_meta_data` fuer uebergebene IDs — aber nur fuer
--   * Mitglieder des aktuellen Workspaces (`app.current_tenant`),
--   * Mitglieder der Organisation dieses Workspaces,
--   * den Aufrufer selbst (`app.current_user_id`, transaktionslokal gesetzt
--     von `/v1/me`, der ohne Workspace laeuft).
-- Ohne beide GUCs liefert sie nichts. Die GUCs setzt die App an genau den
-- Stellen, die auch die RLS-Policies (0037) speisen (core/tenancy.py).
--
-- Haertung nach PostgreSQL-Doku „Writing SECURITY DEFINER Functions Safely":
--   * `search_path = pg_catalog, pg_temp`, alle Tabellen schema-qualifiziert.
--   * EXECUTE nur fuer `who2be_app` (und den Owner): PUBLIC und jede weitere
--     Rolle aus der ACL werden entzogen — auch eine, die Default-Privileges
--     des Images vergeben haetten.
--   * Anlegen und Rechte in derselben Transaktion (der Runner faehrt jede
--     Datei in einer eigenen Transaktion).
--
-- plpgsql statt SQL-Funktion: der Body wird erst beim Aufruf aufgeloest.
-- Existiert `auth.users` nicht (reine Test-DB ohne GoTrue), scheitert erst der
-- Aufruf, nicht die Migration; die Aufrufer fallen dann auf „ohne Profil" zurueck.
--
-- Schema-aware (current_schema()), wie 0036: der Isolations-Test faehrt die
-- Migrationen in einem eigenen Schema.

DO $mig$
DECLARE
    app_schema text := current_schema();
    fn regprocedure;
    grantee_role text;
BEGIN
    EXECUTE format($ddl$
        CREATE OR REPLACE FUNCTION %1$I.w2b_user_profiles(p_ids uuid[])
        RETURNS TABLE (id uuid, email text, raw_user_meta_data jsonb)
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, pg_temp
        AS $fn$
        #variable_conflict use_column
        DECLARE
            v_tenant uuid := NULLIF(current_setting('app.current_tenant', true), '')::uuid;
            v_self   uuid := NULLIF(current_setting('app.current_user_id', true), '')::uuid;
        BEGIN
            IF v_tenant IS NULL AND v_self IS NULL THEN
                RETURN;
            END IF;
            RETURN QUERY
            SELECT u.id, u.email::text, u.raw_user_meta_data
            FROM auth.users u
            WHERE u.id = ANY (p_ids)
              AND (
                    u.id = v_self
                 OR EXISTS (
                        SELECT 1 FROM %1$I.workspace_member m
                        WHERE m.workspace_id = v_tenant AND m.user_id = u.id)
                 OR EXISTS (
                        SELECT 1 FROM %1$I.org_member om
                        JOIN %1$I.workspace w ON w.org_id = om.org_id
                        WHERE w.id = v_tenant AND om.user_id = u.id)
              );
        END
        $fn$
    $ddl$, app_schema);

    fn := format('%I.w2b_user_profiles(uuid[])', app_schema)::regprocedure;

    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', fn);
    -- Explizite Grants (z. B. aus ALTER DEFAULT PRIVILEGES) wegnehmen; nur
    -- Owner und who2be_app bleiben.
    FOR grantee_role IN
        SELECT DISTINCT pg_get_userbyid(a.grantee)
        FROM pg_proc p, aclexplode(p.proacl) a
        WHERE p.oid = fn
          AND a.grantee <> 0
          AND a.grantee <> p.proowner
          AND pg_get_userbyid(a.grantee) <> 'who2be_app'
    LOOP
        EXECUTE format('REVOKE ALL ON FUNCTION %s FROM %I', fn, grantee_role);
    END LOOP;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO who2be_app', fn);
    END IF;
END
$mig$;
