-- GoTrue erwartet ein `auth`-Schema und legt seine Tabellen darin via
-- eigenen Migrationen an. Wir geben ihm nur das Schema vor.
-- Vollumfaengliches self-hosted-Supabase-Init (storage_admin, anon, …)
-- bleibt MS-2 (C1-C6) vorbehalten.
CREATE SCHEMA IF NOT EXISTS auth;
