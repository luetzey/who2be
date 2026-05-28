-- Migration 0010 — api_token.workspace_id (TASK-300)
-- Token-Scope pro Workspace (Plan §2.1.D). Ein Agent-Token gehoert zu genau
-- einem Workspace; der MCP-Server resolved den Workspace anhand des Tokens und
-- ergaenzt /v1/workspaces/{ws_id}/... automatisch. Spalte zunaechst nullable;
-- Backfill in 0013, harter Lock in 0014 (Sub-Task 2.1a-2).

ALTER TABLE api_token
    ADD COLUMN workspace_id uuid REFERENCES workspace (id) ON DELETE CASCADE;

CREATE INDEX api_token_workspace_id_idx ON api_token (workspace_id);
