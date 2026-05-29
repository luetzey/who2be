-- Migration 0016 — playbook_resource_link (Phase 2.2)
-- m:n-Verweis Playbook -> einzelne Bloecke einer Resource (Block-Refs,
-- ADR-0021). `block_id` ist die stabile BlockNote-Block-ID; ein Playbook kann
-- mehrere Bloecke derselben Resource referenzieren, daher ist block_id Teil
-- des Primaerschluessels.
--
-- Defense-in-Depth wie persona_playbook (0004/0014): die beiden Composite-FKs
-- auf (workspace_id, playbook_id) und (workspace_id, resource_id) erzwingen
-- DB-seitig, dass nur Entities desselben Workspaces verknuepft werden.
-- owner_id bleibt Audit-Spalte (created_by). position ordnet die Bloecke im
-- Playbook.

CREATE TABLE playbook_resource_link (
    playbook_id  uuid NOT NULL,
    resource_id  uuid NOT NULL,
    block_id     text NOT NULL,
    workspace_id uuid NOT NULL,
    owner_id     uuid NOT NULL,
    position     smallint NOT NULL DEFAULT 0,
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (playbook_id, resource_id, block_id),
    FOREIGN KEY (workspace_id, playbook_id)
        REFERENCES playbook (workspace_id, id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, resource_id)
        REFERENCES resource (workspace_id, id) ON DELETE CASCADE
);

CREATE INDEX playbook_resource_link_resource_idx
    ON playbook_resource_link (workspace_id, resource_id);
