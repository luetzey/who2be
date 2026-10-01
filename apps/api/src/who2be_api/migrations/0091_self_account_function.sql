-- Migration 0091 — eigene Kontodaten nur ueber `w2b_self_account()`
-- Plan: .claude/plan/2026-10-01-0420_n1b-self-account-function.md
--
-- Ergaenzt 0090 fuer die zwei Lesestellen, die mehr als das Profil brauchen:
--   * DSGVO-Auskunft (`account`-Block): `email`, `created_at`, `last_sign_in_at`,
--   * `/v1/me`: ob ein Passwort gesetzt ist (`has_password`).
-- Beides betrifft ausschliesslich den Aufrufer selbst. Die Funktion kennt deshalb
-- keinen Parameter: sie liefert hoechstens EINE Zeile, die von
-- `app.current_user_id` — die App setzt die GUC transaktionslokal
-- (`scope_to_self`, core/tenancy.py). Ohne GUC liefert sie nichts, auch wenn ein
-- Workspace-Mandant gesetzt ist. `w2b_user_profiles` (0090) bleibt unveraendert
-- schmal (id, email, raw_user_meta_data); Anmeldezeitpunkte und Passwortstatus
-- sind fuer andere Mitglieder nicht lesbar.
--
-- Vom Passwort verlaesst nur der Wahrheitswert die Funktion, nie der Hash.
--
-- Haertung wie 0090 (PostgreSQL-Doku „Writing SECURITY DEFINER Functions
-- Safely"): fester `search_path = pg_catalog, pg_temp`, Tabellen
-- schema-qualifiziert, EXECUTE nur fuer `who2be_app` (und den Owner), PUBLIC und
-- jede weitere Rolle aus der ACL entzogen. plpgsql, damit eine Test-DB ohne
-- GoTrue erst beim Aufruf scheitert, nicht beim Migrieren. Schema-aware
-- (current_schema()) wie 0036/0090.

DO $mig$
DECLARE
    app_schema text := current_schema();
    fn regprocedure;
    grantee_role text;
BEGIN
    EXECUTE format($ddl$
        CREATE OR REPLACE FUNCTION %1$I.w2b_self_account()
        RETURNS TABLE (
            id              uuid,
            email           text,
            created_at      timestamptz,
            last_sign_in_at timestamptz,
            has_password    boolean
        )
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, pg_temp
        AS $fn$
        #variable_conflict use_column
        DECLARE
            v_self uuid := NULLIF(current_setting('app.current_user_id', true), '')::uuid;
        BEGIN
            IF v_self IS NULL THEN
                RETURN;
            END IF;
            RETURN QUERY
            SELECT u.id,
                   u.email::text,
                   u.created_at,
                   u.last_sign_in_at,
                   u.encrypted_password IS NOT NULL AND u.encrypted_password <> ''
            FROM auth.users u
            WHERE u.id = v_self;
        END
        $fn$
    $ddl$, app_schema);

    fn := format('%I.w2b_self_account()', app_schema)::regprocedure;

    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', fn);
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
