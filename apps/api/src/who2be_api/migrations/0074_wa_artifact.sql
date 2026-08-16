-- Migration 0074 — WorkArea-Artefakte: `wa_artifact` (ADR-0047)
-- Plan: .claude/plan/2026-08-13-1200_agent-workarea-knowledge-base.md
--
-- Rohmaterial der Agenten in einer WorkArea (0073): 'doc' traegt eine
-- Block-Liste `[{block_id, kind, level?, md}]` in `content` (Anker-Sprache =
-- ADR-0021, `<artifact_id>#<block_id>`); 'blob' und 'table' referenzieren
-- ueber `content_ref` (blob: sha256 in `wa_blob`/0075 · table: `wa_table.id`,
-- kommt mit 0078). Kein Status-Workflow, keine Versionierung — Nebenlaeufigkeit
-- laeuft optimistisch ueber `rev` (`patch` schreibt `WHERE rev = expected`,
-- 0 Zeilen -> 409 rev_conflict; `append` ist lockfrei `content || $blocks`).
--
-- `occurred_at` ist PFLICHT-Input ohne Server-Fallback auf now() — wer den
-- fachlichen Zeitpunkt nicht kennt, setzt `occurred_precision = 'unknown'`
-- (Timeline-Anforderung N; der partielle Index unten traegt nur datierte
-- Artefakte). `blob_sha256` + `source_system`/`source_url`/`fetched_at` sind
-- Ingest-Provenance (Pipeline B).
--
-- Idempotenz: CREATE via IF NOT EXISTS; Policy via DROP IF EXISTS + CREATE;
-- GRANT idempotent; pg_roles-Guard schuetzt On-Prem/Dev ohne who2be_app
-- (Muster aus 0066/0070).

CREATE TABLE IF NOT EXISTS wa_artifact (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id       uuid NOT NULL,
    area_id            uuid NOT NULL REFERENCES work_area (id) ON DELETE CASCADE,
    type               text NOT NULL CHECK (type IN ('doc', 'table', 'blob')),
    title              text NOT NULL,
    -- Optimistische Nebenlaeufigkeit (rev_conflict-Pfad, s. Kopfkommentar).
    rev                integer NOT NULL DEFAULT 1,
    -- Fachlicher Zeitpunkt — Pflicht-Input, KEIN Default auf now().
    occurred_at        timestamptz NOT NULL,
    occurred_precision text NOT NULL
                       CHECK (occurred_precision IN ('day', 'minute', 'unknown')),
    -- doc: Block-Liste; table/blob: NULL (Inhalt liegt hinter content_ref).
    content            jsonb,
    -- blob: sha256 (wa_blob) · table: wa_table.id (0078).
    content_ref        text,
    -- Ingest-Provenance: Quell-Blob des abgeleiteten Texts.
    blob_sha256        text,
    sensitivity        text NOT NULL DEFAULT 'general'
                       CHECK (sensitivity IN ('general', 'sensitive')),
    source_system      text,
    source_url         text,
    fetched_at         timestamptz,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    updated_by         uuid
);

-- List-/Scope-Pfad: Artefakte einer Area im Workspace.
CREATE INDEX IF NOT EXISTS wa_artifact_area_idx
    ON wa_artifact (workspace_id, area_id);

-- Timeline-Pfad (N): nur fachlich datierte Artefakte; 'unknown' landet im
-- separaten unknown-Bucket und braucht den Index nicht.
CREATE INDEX IF NOT EXISTS wa_artifact_timeline_idx
    ON wa_artifact (workspace_id, occurred_at)
    WHERE occurred_precision <> 'unknown';

-- RLS strikt auf app.current_tenant (Workspace-Isolation, Muster 0066/0070).
DO $$
BEGIN
    EXECUTE 'ALTER TABLE wa_artifact ENABLE ROW LEVEL SECURITY';
    EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON wa_artifact';
    EXECUTE format(
        'CREATE POLICY tenant_isolation ON wa_artifact '
        'USING (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid) '
        'WITH CHECK (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid)',
        'app.current_tenant', '', 'app.current_tenant', ''
    );
END
$$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON wa_artifact TO who2be_app;
    END IF;
END
$$;
