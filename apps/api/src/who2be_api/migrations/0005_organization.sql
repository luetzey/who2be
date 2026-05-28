-- Migration 0005 — organization + org_member (TASK-300)
-- Erste Stufe der Tenant-Hierarchie (User -> org_member -> organization).
-- `kind='personal'` markiert auto-angelegte Personal-Orgs (Backfill 0013),
-- `kind='company'` echte Mandanten. `slug` ist je `kind` eindeutig, damit
-- Personal-Slugs (owner_id-Hex-Prefix) nicht mit Company-Slugs kollidieren.

CREATE TABLE organization (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL,
    slug        text NOT NULL,
    kind        text NOT NULL CHECK (kind IN ('personal', 'company')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (kind, slug)
);

CREATE TABLE org_member (
    org_id      uuid NOT NULL REFERENCES organization (id) ON DELETE CASCADE,
    user_id     uuid NOT NULL,
    role        text NOT NULL CHECK (role IN ('owner', 'admin', 'member')),
    invited_by  uuid,
    joined_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id, user_id)
);

CREATE INDEX org_member_user_id_idx ON org_member (user_id);
