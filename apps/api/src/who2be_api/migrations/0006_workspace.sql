-- Migration 0006 — workspace (TASK-300)
-- Zweite Stufe der Tenant-Hierarchie. Eine Organization haelt ein oder mehrere
-- Workspaces; alle Entities (persona/playbook/api_token) leben innerhalb eines
-- Workspaces. `(org_id, slug)` ist eindeutig, damit der Switcher stabile
-- URL-Pfade /w/{ws_id}/... bauen kann ohne Slug-Kollisionen pro Org.

CREATE TABLE workspace (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      uuid NOT NULL REFERENCES organization (id) ON DELETE CASCADE,
    name        text NOT NULL,
    slug        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (org_id, slug)
);

CREATE INDEX workspace_org_id_idx ON workspace (org_id);
