-- Migration 0094 — `w2b_self_account()` liefert zusaetzlich `email_confirmed`
-- Plan: .claude/plan/2026-10-01-2100_s2b-a1a-email-confirmed.md
--
-- Die offenen Einladungen eines Kontos (S2b, folgende PRs) werden nur
-- angezeigt und angenommen, wenn die E-Mail-Adresse des Kontos bestaetigt ist.
-- Die Bestaetigung steht in `auth.users.email_confirmed_at` (GoTrue). Die App
-- liest `auth.users` nur ueber SECURITY-DEFINER-Funktionen (0090/0093), deshalb
-- bekommt `w2b_self_account()` eine weitere Spalte, einen Wahrheitswert. Der
-- Zeitstempel selbst verlaesst die Funktion nicht.
--
-- 0093 bleibt unveraendert (Migrationen sind unveraenderlich). Weil sich der
-- Rueckgabetyp aendert, reicht `CREATE OR REPLACE` nicht: die Funktion wird
-- in derselben Transaktion entfernt und neu angelegt (der Runner faehrt jede
-- Datei in einer Transaktion, core/migrations.py). Aufrufer selektieren
-- Spalten per Namen und bleiben gueltig.
--
-- Semantik und Haertung wie 0093: keine Parameter, hoechstens EINE Zeile, die
-- von `app.current_user_id`; ohne GUC keine Zeile. Fester
-- `search_path = pg_catalog, pg_temp`, Tabellen schema-qualifiziert, EXECUTE
-- nur fuer `who2be_app` (und den Owner), PUBLIC und jede weitere Rolle aus der
-- ACL entzogen. plpgsql, damit eine Test-DB ohne GoTrue erst beim Aufruf
-- scheitert. Schema-aware (current_schema()) wie 0090/0093.

DO $mig$
DECLARE
    app_schema text := current_schema();
    fn regprocedure;
    grantee_role text;
BEGIN
    EXECUTE format('DROP FUNCTION IF EXISTS %I.w2b_self_account()', app_schema);

    EXECUTE format($ddl$
        CREATE FUNCTION %1$I.w2b_self_account()
        RETURNS TABLE (
            id              uuid,
            email           text,
            created_at      timestamptz,
            last_sign_in_at timestamptz,
            has_password    boolean,
            email_confirmed boolean
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
                   u.encrypted_password IS NOT NULL AND u.encrypted_password <> '',
                   u.email_confirmed_at IS NOT NULL
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
