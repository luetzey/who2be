-- Migration 0007 — workspace_member (TASK-300)
-- Mitgliedschaft + Rolle pro Workspace. In Phase 2.1 nur fuer den Personal-
-- Workspace-Owner gefuellt (Backfill 0013), in Phase 2.3 echt fuer Einladungen
-- benutzt. Die Rollen-Hierarchie ist admin > editor > viewer; Promote auf
-- Status='active' bleibt admin-only (siehe Plan §2.3.B).

CREATE TABLE workspace_member (
    workspace_id  uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    user_id       uuid NOT NULL,
    role          text NOT NULL CHECK (role IN ('admin', 'editor', 'viewer')),
    joined_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, user_id)
);

CREATE INDEX workspace_member_user_id_idx ON workspace_member (user_id);
