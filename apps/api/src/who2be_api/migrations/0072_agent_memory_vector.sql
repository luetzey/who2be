-- Migration 0072 — Vektor-Spalte auf dem Agent-Memory (ADR-0046, Welle 3)
--
-- Loest die zweite offen gelassene Stelle ein: ADR-0044 §70-71 nennt pgvector
-- ausdruecklich als „Stufe-B-Pfad". Bis hierher versprach der MCP-Docstring von
-- `search_memory` dem Modell, das Gedaechtnis werde „semantisch" durchsucht —
-- implementiert waren FTS('simple') + ILIKE + pg_trgm. `pg_trgm` ist
-- ZEICHENbasiert: „Kunde bevorzugt Kontakt per E-Mail" und „wie will der Kunde
-- erreicht werden" kommen auf eine Similarity von 0,14, eine deutsche Anfrage
-- gegen englischen Inhalt auf 0,03 — beide weit unter der Suchschwelle 0,3.
--
-- Memory bekommt eine EIGENE Spalte statt eines Platzes in `content_chunk`
-- (ADR-0046 §2): Chunks sind abgeleitet, regenerierbar und versionsgebunden,
-- Memories dagegen zur Laufzeit geschrieben, mutabel, agent-gebunden und mit
-- eigenem Kurations-Lebenszyklus (pending/active/rejected). Geteilt werden der
-- EmbeddingPort, die Dimension und die Rang-Fusion — nicht die Tabelle.
--
-- KEIN Chunking: `fact` ist auf 300 Zeichen begrenzt (CHECK in 0066), also
-- genau ein Vektor pro Zeile. Und KEIN ANN-Index: `MEMORY_MAX_PER_AGENT` = 500
-- deckelt hart, und jede Query filtert vorher auf (workspace_id, agent_id) —
-- ein sequentieller Scan ueber hoechstens 500 Zeilen ist schneller, als ein
-- ANN-Index sich rentiert, und waere zudem nur approximativ.
--
-- FAIL-SOFT wie 0071: `CREATE EXTENSION vector` scheitert hart auf einem
-- Postgres ohne pgvector — dem Normalfall einer selbst gehosteten Instanz. Ein
-- additives Feature darf dort nicht die Migrationskette abbrechen. Fehlt die
-- Extension, entsteht die Spalte nicht; `memory_repository.vector_supported`
-- prueft ihre Existenz und laesst das Retrieval dann rein lexikalisch.
--
-- Extension-Schema dynamisch aufgeloest (Muster 0066/0071): lokal `public`,
-- Supabase `extensions`, Test-Schemata eigenes.

DO $$
DECLARE
    ext_schema text;
BEGIN
    BEGIN
        CREATE EXTENSION IF NOT EXISTS vector;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE
            'pgvector nicht verfuegbar (%) — Memory-Retrieval bleibt lexikalisch '
            '(FTS + ILIKE + Trigram), alles andere unveraendert.', SQLERRM;
        RETURN;
    END;

    SELECT n.nspname INTO ext_schema
    FROM pg_extension e
    JOIN pg_namespace n ON n.oid = e.extnamespace
    WHERE e.extname = 'vector';

    EXECUTE format(
        'ALTER TABLE agent_memory ADD COLUMN IF NOT EXISTS content_vector %I.vector(384)',
        ext_schema
    );

    -- Arbeitsvorrat des Backfills. Partial, damit der Index nur so lange etwas
    -- kostet, wie es Nachzuegler gibt.
    EXECUTE
        'CREATE INDEX IF NOT EXISTS agent_memory_missing_vector_idx '
        'ON agent_memory (workspace_id, agent_id) '
        'WHERE content_vector IS NULL';
END
$$;
