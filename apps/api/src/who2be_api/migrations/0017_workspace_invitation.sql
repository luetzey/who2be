-- Migration 0017 — workspace_invitation (Phase 2.3-0)
-- Einladungen in einen Workspace mit Rolle. Der Klartext-Token geht per Mail
-- raus; persistiert wird nur der SHA-256-Hash (ADR-0006-Linie, analog
-- api_token.token_hash). Single-Use + Expiry schuetzen vor Replay; der
-- partial unique Index verhindert zwei offene Invitations fuer dieselbe Mail
-- im selben Workspace. Auswertender Code (Endpoints, Accept-Flow) folgt in
-- einer spaeteren Phase-2.3-PR — siehe ADR-0023.
--
-- Idempotenz: CREATE TABLE/INDEX mit IF NOT EXISTS, damit ein manuelles
-- Re-Apply (Phase-Idempotenztest) ein No-op bleibt.

CREATE TABLE IF NOT EXISTS workspace_invitation (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    email        text NOT NULL,
    role         text NOT NULL CHECK (role IN ('admin', 'editor', 'viewer')),
    token_hash   text NOT NULL UNIQUE,
    expires_at   timestamptz NOT NULL,
    created_by   uuid NOT NULL,
    accepted_at  timestamptz,
    revoked_at   timestamptz,
    created_at   timestamptz NOT NULL DEFAULT now()
);

-- Max. eine offene (noch nicht akzeptierte, nicht widerrufene) Invitation je
-- (Workspace, Mail). lower(email) macht den Schutz case-insensitive.
CREATE UNIQUE INDEX IF NOT EXISTS workspace_invitation_open_uniq
    ON workspace_invitation (workspace_id, lower(email))
    WHERE accepted_at IS NULL AND revoked_at IS NULL;
