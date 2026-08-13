-- Migration 0075 — Content-addressed Blob-Katalog: `wa_blob` (ADR-0048)
-- Plan: .claude/plan/2026-08-13-1200_agent-workarea-knowledge-base.md
--
-- Postgres-Katalog der binaeren Originale im BlobStore (MinIO/S3 hinter Port,
-- ADR-0048). Der Objekt-Key ist content-addressed
-- (`blobs/{workspace_id}/{sha256}`), deshalb ist die Identitaet der Zeile
-- `PK (workspace_id, sha256)` — Dedup pro Workspace, bewusst KEIN
-- Cross-Workspace-Dedup (Workspace-Praefix macht GDPR-Purge/-Export trivial).
-- Ingest (Pipeline B) upsertet hier VOR dem Artifact-Write in derselben
-- Transaktion; ein Blob-PUT ohne Katalog-Zeile ist ein Orphan fuer den
-- Purge-Sweep (>24 h).
--
-- `source_url`/`fetched_at` sind URL-Ingest-Provenance; Datei-Uploads lassen
-- beide leer.
--
-- Idempotenz: CREATE via IF NOT EXISTS; Policy via DROP IF EXISTS + CREATE;
-- GRANT idempotent; pg_roles-Guard schuetzt On-Prem/Dev ohne who2be_app
-- (Muster aus 0066/0070).

CREATE TABLE IF NOT EXISTS wa_blob (
    workspace_id uuid NOT NULL,
    sha256       text NOT NULL,
    size_bytes   bigint NOT NULL,
    media_type   text NOT NULL,
    -- Objekt-Key im BlobStore: blobs/{workspace_id}/{sha256} (ADR-0048).
    storage_key  text NOT NULL,
    source_url   text,
    fetched_at   timestamptz,
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, sha256)
);

-- RLS strikt auf app.current_tenant (Workspace-Isolation, Muster 0066/0070).
DO $$
BEGIN
    EXECUTE 'ALTER TABLE wa_blob ENABLE ROW LEVEL SECURITY';
    EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON wa_blob';
    EXECUTE format(
        'CREATE POLICY tenant_isolation ON wa_blob '
        'USING (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid) '
        'WITH CHECK (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid)',
        'app.current_tenant', '', 'app.current_tenant', ''
    );
END
$$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON wa_blob TO who2be_app;
    END IF;
END
$$;
