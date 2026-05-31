-- Migration 0028 — playbook_composition (Gap 2.1, ADR-0024)
-- Self-m:n: parent (Composite) -> child (Sub-Playbook), geordnet via position.
-- Composite-FKs auf (workspace_id, id) erzwingen Same-Workspace (wie 0016).
-- CHECK verhindert direkte Selbst-Referenz; transitive Zyklen prueft der
-- Service via WITH RECURSIVE vor dem Insert.
-- Idempotent: CREATE TABLE/INDEX IF NOT EXISTS, Constraint via pg_constraint-Guard.

CREATE TABLE IF NOT EXISTS playbook_composition (
    parent_id    uuid NOT NULL,
    child_id     uuid NOT NULL,
    workspace_id uuid NOT NULL,
    owner_id     uuid NOT NULL,
    position     smallint NOT NULL DEFAULT 0,
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (parent_id, child_id),
    CONSTRAINT playbook_composition_no_self CHECK (parent_id <> child_id),
    FOREIGN KEY (workspace_id, parent_id)
        REFERENCES playbook (workspace_id, id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, child_id)
        REFERENCES playbook (workspace_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS playbook_composition_child_idx
    ON playbook_composition (workspace_id, child_id);
