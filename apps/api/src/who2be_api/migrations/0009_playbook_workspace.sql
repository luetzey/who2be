-- Migration 0009 — playbook.workspace_id (TASK-300)
-- Analog 0008 fuer playbook. Spalte zunaechst nullable; Backfill in 0013,
-- harter Lock in 0014 (Sub-Task 2.1a-2). owner_id bleibt als Audit-Spalte.

ALTER TABLE playbook
    ADD COLUMN workspace_id uuid REFERENCES workspace (id) ON DELETE CASCADE;

CREATE INDEX playbook_workspace_id_idx ON playbook (workspace_id);
