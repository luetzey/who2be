-- Migration 0049 — OAuth-Remote-MCP-Connector (Authorization Server)
--
-- Ermoeglicht Endnutzern, ihren LLM-Client (Claude/ChatGPT) per Remote-MCP-URL +
-- OAuth-Login mit Who2Be zu verbinden, statt Token-Copy-Paste. Who2Be wird zum
-- OAuth-2.1-Authorization-Server (MCP-Authorization-Spec: RFC 9728/8414/7591/8707).
--
-- Vier Bausteine:
--  1. oauth_client            — dynamisch registrierte Clients (DCR, RFC 7591),
--     public clients (PKCE, kein client_secret).
--  2. oauth_authorization_code — kurzlebiger, single-use Authorization-Code mit
--     PKCE-Challenge; bindet den spaeteren Token an User + Workspace + Agent.
--  3. api_token.expires_at     — Access-Token-Ablauf (OAuth gibt kurzlebige
--     Tokens aus; NULL = nicht-OAuth-Bestandstoken, unveraendert).
--  4. oauth_refresh_token      — rotierende Refresh-Tokens; rotated_from bildet
--     die Rotationskette fuer Replay-Detection.
--
-- Idempotent: CREATE TABLE / ADD COLUMN IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS oauth_client (
    client_id text PRIMARY KEY,
    client_name text,
    redirect_uris text[] NOT NULL,
    token_endpoint_auth_method text NOT NULL DEFAULT 'none',
    grant_types text[] NOT NULL DEFAULT ARRAY['authorization_code', 'refresh_token'],
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (array_length(redirect_uris, 1) >= 1)
);

CREATE TABLE IF NOT EXISTS oauth_authorization_code (
    code_hash text PRIMARY KEY,
    client_id text NOT NULL REFERENCES oauth_client (client_id) ON DELETE CASCADE,
    redirect_uri text NOT NULL,
    code_challenge text NOT NULL,
    user_id uuid NOT NULL,
    workspace_id uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    agent_id uuid NOT NULL REFERENCES agent (id) ON DELETE CASCADE,
    role text NOT NULL,
    resource text NOT NULL,
    scope text,
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz
);

CREATE INDEX IF NOT EXISTS oauth_authorization_code_expires_idx
    ON oauth_authorization_code (expires_at);

-- Access-Token-Ablauf: NULL bei Bestandstoken (unveraendert gueltig bis Revoke),
-- gesetzt bei OAuth-Access-Tokens (kurzlebig). Der Auth-Pfad prueft
-- `expires_at IS NULL OR expires_at > now()`.
ALTER TABLE api_token ADD COLUMN IF NOT EXISTS expires_at timestamptz;

CREATE TABLE IF NOT EXISTS oauth_refresh_token (
    token_hash text PRIMARY KEY,
    api_token_id uuid NOT NULL REFERENCES api_token (id) ON DELETE CASCADE,
    client_id text NOT NULL REFERENCES oauth_client (client_id) ON DELETE CASCADE,
    rotated_from text,
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz
);

CREATE INDEX IF NOT EXISTS oauth_refresh_token_api_token_idx
    ON oauth_refresh_token (api_token_id);
