-- Migration 0003 — playbook + playbook_version (TASK-176)
-- Versionierung analog persona (ADR-0004). `tags`, `triggers` und `type` sind
-- aus der aktuellen Version denormalisiert, damit `list_playbooks` ohne Join
-- filtern kann; der vollstaendige Inhalt liegt in `playbook_version.content`.

CREATE TABLE playbook (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id        uuid NOT NULL,
    name            text NOT NULL,
    current_version int NOT NULL DEFAULT 1,
    type            text NOT NULL,
    tags            text[] NOT NULL DEFAULT '{}',
    triggers        text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    -- Ziel fuer den Composite-FK aus persona_playbook (Owner-Isolation).
    UNIQUE (owner_id, id)
);

CREATE INDEX playbook_owner_id_idx ON playbook (owner_id);
CREATE INDEX playbook_tags_idx ON playbook USING gin (tags);

CREATE TABLE playbook_version (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    playbook_id uuid NOT NULL REFERENCES playbook (id) ON DELETE CASCADE,
    version     int NOT NULL,
    content     jsonb NOT NULL,
    created_by  uuid NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (playbook_id, version)
);
