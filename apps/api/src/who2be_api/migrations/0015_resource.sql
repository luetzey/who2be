-- Migration 0015 — resource + resource_version (Phase 2.2)
-- Resources sind die zweite Wissensebene: versionierter Block-Editor-Inhalt
-- (BlockNote-Dokument, ADR-0022). Aufbau analog playbook/persona (ADR-0004)
-- inkl. Status-pro-Version (ADR-0020).
--
-- Mandantenschluessel ist von Anfang an workspace_id (kein owner_id-Schwenk
-- noetig wie bei persona/playbook in 0008-0014). owner_id bleibt als
-- Audit-Spalte (created_by-Bruecke). UNIQUE (workspace_id, id) ist Ziel des
-- Composite-FK aus playbook_resource_link (0016).

CREATE TABLE resource (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    owner_id        uuid NOT NULL,
    name            text NOT NULL,
    current_version int NOT NULL DEFAULT 1,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, id)
);

CREATE INDEX resource_workspace_id_idx ON resource (workspace_id);

CREATE TABLE resource_version (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id uuid NOT NULL REFERENCES resource (id) ON DELETE CASCADE,
    version     int NOT NULL,
    content     jsonb NOT NULL,
    status      text NOT NULL DEFAULT 'inactive'
        CHECK (status IN ('draft', 'review', 'active', 'inactive')),
    created_by  uuid NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (resource_id, version)
);

-- DB-erzwungene Invariante "max. 1 Draft / 1 Review / 1 Active je Resource"
-- (Partial Unique Indices, identisch zu 0011 fuer persona/playbook).
CREATE UNIQUE INDEX resource_version_active_uniq
    ON resource_version (resource_id) WHERE status = 'active';
CREATE UNIQUE INDEX resource_version_draft_uniq
    ON resource_version (resource_id) WHERE status = 'draft';
CREATE UNIQUE INDEX resource_version_review_uniq
    ON resource_version (resource_id) WHERE status = 'review';
