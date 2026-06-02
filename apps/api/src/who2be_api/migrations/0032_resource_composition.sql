-- Migration 0032 — resource_composition (Track E, §3.3)
-- Self-m:n: parent (Resource) -> child (Sub-Resource), geordnet via position.
-- Verbindet zwei bestehende Muster:
--   * playbook_resource_link (0016/0021): `link_scope` resource/block +
--     nullable `block_id`, ein Heading-Anker je Block-Link, ein Volldokument-
--     Link je (parent, child).
--   * playbook_composition (0028): azyklische Self-Relation, transitive Zyklen
--     prueft der Service via WITH RECURSIVE vor dem Insert.
--
-- Die beiden Composite-FKs auf (workspace_id, parent_id) und
-- (workspace_id, child_id) erzwingen DB-seitig Same-Workspace (wie 0016/0028);
-- owner_id bleibt Audit-Spalte (created_by). CHECK verhindert direkte
-- Selbst-Referenz.
--
-- Idempotent: CREATE TABLE/INDEX IF NOT EXISTS; die Constraints leben inline
-- im CREATE TABLE und werden mit ihm nur einmal angelegt.

CREATE TABLE IF NOT EXISTS resource_composition (
    parent_id    uuid NOT NULL,
    child_id     uuid NOT NULL,
    block_id     text,
    workspace_id uuid NOT NULL,
    owner_id     uuid NOT NULL,
    position     smallint NOT NULL DEFAULT 0,
    link_scope   text NOT NULL DEFAULT 'resource',
    created_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT resource_composition_no_self CHECK (parent_id <> child_id),
    CONSTRAINT resource_composition_scope_check
        CHECK (link_scope IN ('resource', 'block')),
    -- Pflicht-/Verbot-Kopplung wie playbook_resource_link (0021):
    -- 'resource' -> block_id NULL; 'block' -> block_id gesetzt.
    CONSTRAINT resource_composition_scope_block_id_check
        CHECK (
            (link_scope = 'resource' AND block_id IS NULL)
            OR (link_scope = 'block' AND block_id IS NOT NULL)
        ),
    FOREIGN KEY (workspace_id, parent_id)
        REFERENCES resource (workspace_id, id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, child_id)
        REFERENCES resource (workspace_id, id) ON DELETE CASCADE
);

-- Genau ein 'resource'-Link (Volldokument) je (parent, child).
CREATE UNIQUE INDEX IF NOT EXISTS resource_composition_resource_scope_uniq
    ON resource_composition (parent_id, child_id)
    WHERE link_scope = 'resource';

-- Block-Links: ein Anker je (parent, child, block_id).
CREATE UNIQUE INDEX IF NOT EXISTS resource_composition_block_scope_uniq
    ON resource_composition (parent_id, child_id, block_id)
    WHERE link_scope = 'block';

-- Reverse-Lookup (used_by / Zyklus-Guard): Kinder eines Workspace schnell finden.
CREATE INDEX IF NOT EXISTS resource_composition_child_idx
    ON resource_composition (workspace_id, child_id);
