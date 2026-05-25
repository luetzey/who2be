-- Idempotente Init-Saetze. `supabase/postgres` bringt die Standard-Rollen
-- (anon, authenticated, service_role, supabase_admin, supabase_auth_admin)
-- bereits beim ersten Start ueber sein eigenes Init-Script mit. Hier nur
-- Sicherheitsnetz fuer den unwahrscheinlichen Fall, dass das Image-Init
-- aus irgendeinem Grund nicht durchgelaufen ist.

CREATE SCHEMA IF NOT EXISTS auth;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOLOGIN NOINHERIT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        CREATE ROLE service_role NOLOGIN NOINHERIT BYPASSRLS;
    END IF;
END$$;
