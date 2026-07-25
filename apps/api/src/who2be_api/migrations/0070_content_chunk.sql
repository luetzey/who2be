-- Migration 0070 — Passage-Ebene fuer Retrieval (`content_chunk`, ADR-0046)
--
-- Materialisiert die AKTIVE Version jedes Inhaltselements in Passagen, damit
-- Agenten Abschnitte finden statt ganzer Aggregate. Entity-Ranking allein
-- spart keinen Kontext: ein Treffer „Playbook X" zwingt weiter zum
-- `fetch_playbook` ueber den Volltext.
--
-- Ersetzt die in ADR-0037 §53-54 zugesagten, nie angelegten Per-Tabelle-
-- `tsvector`-Spalten: EINE Textebene statt vier, und sie traegt spaeter auch
-- den Vektor (ADR-0046 Welle 2, Spalte `content_vector`).
--
-- Schnitt entlang der Heading-Bloecke: jeder Heading-Block beginnt einen Chunk,
-- `block_id` ist damit exakt der bestehende Block-Anker aus ADR-0021 — ein
-- Treffer ist unmittelbar als `"<uuid>#<block_id>"` referenzierbar, es entsteht
-- KEINE zweite Ankersprache. `heading_path` traegt die Ueberschriften-Kette der
-- Vorfahren; sie geht in den Index, aber nicht in die ausgelieferte Passage
-- (Kontext ohne Text-Duplikat).
--
-- FTS-Config pro Sprache (Abweichung von 0066): seit ADR-0045 ist jedes
-- Element EINSPRACHIG, deshalb ist Stemming hier sinnvoll — 'german' findet
-- „Reklamation" in „Reklamationen", 'simple' nicht. Das Locale-Set ist offen
-- (BCP-47-artig, `de-at`), daher entscheidet das Sprach-Praefix; unbekannte
-- Sprachen fallen auf 'simple' zurueck (kein Stemming, aber auch kein Fehler).
-- Die CASE-Zweige sind regconfig-LITERALE — nur so ist der Ausdruck immutable
-- und in einer Generated Column zulaessig (`locale::regconfig` waere STABLE).
--
-- Kein FK auf die Entity: `entity_id` ist polymorph ueber fuenf Tabellen. Die
-- Suche joint ohnehin auf die Entity-Tabelle (sie braucht `name`/`locale` fuer
-- den Treffer), deshalb sind verwaiste Chunks nicht auffindbar und damit
-- harmlos; der Backfill-CLI raeumt sie zusaetzlich weg. Chunks sind ABGELEITET
-- und jederzeit aus der aktiven Version regenerierbar — ein Neuaufbau
-- verliert nichts.
--
-- Idempotenz: CREATE via IF NOT EXISTS; Policy via DROP IF EXISTS + CREATE;
-- GRANT idempotent; pg_roles-Guard schuetzt On-Prem/Dev ohne who2be_app
-- (Muster aus 0066).

CREATE TABLE IF NOT EXISTS content_chunk (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id  uuid NOT NULL,
    entity_type   text NOT NULL CHECK (entity_type IN (
                      'persona', 'playbook', 'resource',
                      'system_prompt_template', 'external_tool')),
    entity_id     uuid NOT NULL,
    version       integer NOT NULL,
    -- Sprache der Version; steuert die FTS-Config der generierten Spalte.
    locale        text NOT NULL,
    -- Anker-Heading-Block der Passage. NULL, wenn die Passage keinem Block
    -- entspricht (Beschreibungs-Chunk, Text vor dem ersten Heading,
    -- blocklose Aggregate wie external_tool).
    block_id      text,
    -- Ueberschriften-Kette der Vorfahren, z. B. „Reklamation > Eskalation".
    heading_path  text NOT NULL DEFAULT '',
    -- Position der Passage innerhalb der Version (stabile Reihenfolge).
    ord           integer NOT NULL,
    text          text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    search        tsvector GENERATED ALWAYS AS (
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

-- Rebuild/Cleanup laeuft immer ueber (workspace, typ, entity).
CREATE INDEX IF NOT EXISTS content_chunk_entity_idx
    ON content_chunk (workspace_id, entity_type, entity_id);

-- Trefferpfad der Passage-Suche.
CREATE INDEX IF NOT EXISTS content_chunk_search_idx
    ON content_chunk USING gin (search);

-- Eine Passage pro (Entity, Version, Sprache, Position) — macht den Rebuild
-- idempotent und faengt doppelte Einspielungen ab.
CREATE UNIQUE INDEX IF NOT EXISTS content_chunk_slot_idx
    ON content_chunk (entity_type, entity_id, version, locale, ord);

-- RLS strikt auf app.current_tenant (Workspace-Isolation, Muster 0066).
DO $$
BEGIN
    EXECUTE 'ALTER TABLE content_chunk ENABLE ROW LEVEL SECURITY';
    EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON content_chunk';
    EXECUTE format(
        'CREATE POLICY tenant_isolation ON content_chunk '
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
        GRANT SELECT, INSERT, UPDATE, DELETE ON content_chunk TO who2be_app;
    END IF;
END
$$;
