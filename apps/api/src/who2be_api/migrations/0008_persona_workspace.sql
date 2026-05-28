-- Migration 0008 — persona.workspace_id (TASK-300)
-- Anbindung der Persona-Tabelle an die Workspace-Hierarchie. Spalte ist
-- zunaechst nullable: der Backfill in 0013 fuellt sie pro vorhandenem
-- owner_id, der harte Lock (SET NOT NULL + UNIQUE(workspace_id, id) +
-- Composite-FK-Switch auf persona_playbook) erfolgt in 0014_finalize_workspace_id
-- zusammen mit dem Repository-Refactor in Sub-Task 2.1a-2.
--
-- owner_id bleibt als Audit-Spalte (created_by) erhalten — Bruecke fuer den
-- Backfill und Quelle fuer status_history.changed_by-Defaults.

ALTER TABLE persona
    ADD COLUMN workspace_id uuid REFERENCES workspace (id) ON DELETE CASCADE;

CREATE INDEX persona_workspace_id_idx ON persona (workspace_id);
