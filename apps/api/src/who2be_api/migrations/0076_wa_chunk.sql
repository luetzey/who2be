-- Migration 0076 — WorkArea-Passagen fuer Retrieval: `wa_chunk` (ADR-0047)
-- Plan: .claude/plan/2026-08-13-1200_agent-workarea-knowledge-base.md
--
-- Passage-Ebene der doc-Artefakte (0074) nach der 0070-Vorlage
-- (`content_chunk`, ADR-0046): jeder Heading-Block beginnt einen Chunk,
-- `block_id` ist der bestehende Block-Anker aus ADR-0021 — ein Suchtreffer
-- ist unmittelbar `read_artifact(id, anchor)`-faehig, es entsteht KEINE
-- zweite Ankersprache. `heading_path` traegt die Ueberschriften-Kette der
-- Vorfahren in den Index, nicht in die ausgelieferte Passage.
--
-- BEWUSST eigene Tabelle statt Erweiterung von `content_chunk`: WorkArea-
-- Material und kuratierter Content bleiben getrennte Indizes (Spec §10.1) —
-- die Scope-Filter (Area-Grants) unterscheiden sich grundsaetzlich vom
-- Entity-Scope der Content-Suche. `area_id` ist dafuer denormalisiert
-- (Filter ohne Join auf wa_artifact).
--
-- FTS-Config pro Sprache exakt wie 0070: regconfig-LITERALE in den
-- CASE-Zweigen (nur so immutable und in einer Generated Column zulaessig),
-- Sprach-Praefix entscheidet, unbekannte Sprachen fallen auf 'simple' zurueck.
--
-- Chunks sind ABGELEITET und jederzeit aus dem Artifact-Content regenerierbar;
-- der FK auf wa_artifact raeumt sie beim Loeschen mit ab.
--
-- Idempotenz: CREATE via IF NOT EXISTS; Policy via DROP IF EXISTS + CREATE;
-- GRANT idempotent; pg_roles-Guard schuetzt On-Prem/Dev ohne who2be_app
-- (Muster aus 0066/0070).

CREATE TABLE IF NOT EXISTS wa_chunk (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL,
    artifact_id  uuid NOT NULL REFERENCES wa_artifact (id) ON DELETE CASCADE,
    -- Denormalisiert fuer den Area-Scope-Filter (readable_area_ids) ohne Join.
    area_id      uuid NOT NULL,
    -- Anker-Block der Passage (ADR-0021-Sprache, s. Kopfkommentar).
    block_id     text NOT NULL,
    -- Ueberschriften-Kette der Vorfahren, z. B. „Reklamation > Eskalation".
    heading_path text NOT NULL DEFAULT '',
    -- Position der Passage innerhalb des Artefakts (stabile Reihenfolge).
    ord          integer NOT NULL,
    text         text NOT NULL,
    -- Sprache der Passage; steuert die FTS-Config der generierten Spalte.
    locale       text NOT NULL,
    search       tsvector GENERATED ALWAYS AS (
                     to_tsvector(
                         CASE split_part(locale, '-', 1)
                             WHEN 'de' THEN 'german'::regconfig
                             WHEN 'en' THEN 'english'::regconfig
                             ELSE 'simple'::regconfig
                         END,
                         coalesce(heading_path, '') || ' ' || text
                     )
                 ) STORED
);

-- Scope-Pfad der WorkArea-Suche (Area-Filter VOR Ranking).
CREATE INDEX IF NOT EXISTS wa_chunk_area_idx
    ON wa_chunk (workspace_id, area_id);

-- Rebuild/Cleanup laeuft pro Artifact.
CREATE INDEX IF NOT EXISTS wa_chunk_artifact_idx
    ON wa_chunk (artifact_id);

-- Trefferpfad der Passage-Suche.
CREATE INDEX IF NOT EXISTS wa_chunk_search_idx
    ON wa_chunk USING gin (search);

-- Eine Passage pro (Artifact, Anker-Block, Position) — macht den Rebuild
-- idempotent und faengt doppelte Einspielungen ab.
CREATE UNIQUE INDEX IF NOT EXISTS wa_chunk_slot_idx
    ON wa_chunk (artifact_id, block_id, ord);

-- RLS strikt auf app.current_tenant (Workspace-Isolation, Muster 0066/0070).
DO $$
BEGIN
    EXECUTE 'ALTER TABLE wa_chunk ENABLE ROW LEVEL SECURITY';
    EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON wa_chunk';
    EXECUTE format(
        'CREATE POLICY tenant_isolation ON wa_chunk '
        'USING (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid) '
        'WITH CHECK (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid)',
        'app.current_tenant', '', 'app.current_tenant', ''
    );
END
$$;

-- Abgeleitete Daten: der Rebuild loescht und schreibt neu, daher DELETE.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON wa_chunk TO who2be_app;
    END IF;
END
$$;
