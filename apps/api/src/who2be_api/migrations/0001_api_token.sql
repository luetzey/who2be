-- Migration 0001 — api_token (TASK-175)
-- Eigene API-Token-Tabelle fuer Agenten-Auth (ADR-0006).
-- owner_id verweist auf Supabase auth.users.id; keine lokale User-Tabelle (MVP).
-- token_hash haelt ausschliesslich den SHA-256-Hash — der Klartext wird nie
-- gespeichert, nur einmalig bei der Erstellung zurueckgegeben.

CREATE TABLE api_token (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id     uuid NOT NULL,
    name         text NOT NULL,
    token_hash   text NOT NULL UNIQUE,
    created_at   timestamptz NOT NULL DEFAULT now(),
    last_used_at timestamptz,
    revoked_at   timestamptz
);

CREATE INDEX api_token_owner_id_idx ON api_token (owner_id);
