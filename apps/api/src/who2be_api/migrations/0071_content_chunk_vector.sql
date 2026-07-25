-- Migration 0071 — Vektor-Spalte auf der Passage-Ebene (ADR-0046, Welle 2)
--
-- Ergaenzt `content_chunk` (0070) um `content_vector`. Semantik wird damit
-- ADDITIV: die Spalte ist NULLABLE, und ohne Werte laeuft die Suche unveraendert
-- im Volltext-Modus weiter. Kein Backfill in dieser Migration — die Vektoren
-- entstehen best-effort beim Schreiben und per CLI (`who2be-chunk-backfill`),
-- weil ihre Berechnung in Python liegt und eine SQL-Migration sie nicht
-- nachbauen kann.
--
-- FAIL-SOFT, und das ist der Kern dieser Migration: `CREATE EXTENSION vector`
-- scheitert HART auf einem Postgres, auf dem pgvector nicht installiert ist
-- ("could not open extension control file"). Genau das ist der Normalfall einer
-- selbst gehosteten On-Prem-Instanz auf einem Standard-Postgres. Ohne den
-- EXCEPTION-Block wuerde ein Update dort die Migrationskette abbrechen und die
-- App nicht mehr starten — fuer ein rein additives Feature ein voellig
-- unangemessener Preis. Fehlt die Extension, wird die Spalte NICHT angelegt;
-- der Code prueft ihre Existenz und bleibt dann im Volltext-Modus
-- (`content_chunk_repository.vector_supported`).
--
-- Name bewusst `content_vector`, NICHT `embedding`: `embedding_mode`
-- (Migrationen 0040/0041) bezeichnet bereits die *Einbettung ins Prompt*
-- (`lazy`/`inline`) und darf damit nicht kollidieren.
--
-- 384 Dimensionen — passend zu den gaengigen kleinen multilingualen
-- Satz-Encodern (z. B. paraphrase-multilingual-MiniLM-L12-v2). Die Dimension
-- ist im Schema fixiert; ein Modellwechsel auf eine andere Dimension braucht
-- eine neue Migration UND einen vollstaendigen Re-Embed. Deshalb prueft der
-- EmbeddingPort die Dimension beim Start gegen `EMBEDDING_DIMENSIONS`.
--
-- Extension-Schema wird DYNAMISCH aufgeloest (Muster aus 0066): lokal landet
-- `vector` in `public`, bei Supabase in `extensions`, in isolierten
-- Test-Schemata woanders. Ein unqualifiziertes `vector` im Spaltentyp haengt am
-- `search_path` und bricht deshalb in genau einer dieser Umgebungen.
--
-- KEIN ANN-Index (IVFFlat/HNSW) in v1 — bewusst, nicht vergessen: pro Workspace
-- liegen die Passagen in der Groessenordnung 10^3, und die Suche filtert vorher
-- hart auf `workspace_id` + `entity_type` (+ ggf. die zugewiesenen IDs). Ein
-- sequentieller Scan ueber diese Teilmenge ist schneller, als ein ANN-Index sich
-- rentiert — und ANN waere zudem approximativ. HNSW kommt, wenn Messwerte es
-- fordern.
--
-- Idempotent: die Extension via IF NOT EXISTS, die Spalte via ADD COLUMN IF NOT
-- EXISTS; ein zweiter Lauf auf einer Instanz, die pgvector inzwischen bekommen
-- hat, legt die Spalte nach (die Migration selbst laeuft nur einmal — dafuer
-- gibt es `who2be-chunk-backfill`, das ohnehin neu aufbaut).

DO $$
DECLARE
    ext_schema text;
BEGIN
    BEGIN
        CREATE EXTENSION IF NOT EXISTS vector;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE
            'pgvector nicht verfuegbar (%) — semantische Suche bleibt aus, '
            'Volltext-Suche laeuft unveraendert weiter.', SQLERRM;
        RETURN;
    END;

    SELECT n.nspname INTO ext_schema
    FROM pg_extension e
    JOIN pg_namespace n ON n.oid = e.extnamespace
    WHERE e.extname = 'vector';

    EXECUTE format(
        'ALTER TABLE content_chunk ADD COLUMN IF NOT EXISTS content_vector %I.vector(384)',
        ext_schema
    );

    -- Findet die Passagen, denen noch ein Vektor fehlt (Backfill-Pfad).
    -- Partial, damit der Index nur so lange etwas kostet, wie es Nachzuegler
    -- gibt.
    EXECUTE
        'CREATE INDEX IF NOT EXISTS content_chunk_missing_vector_idx '
        'ON content_chunk (workspace_id, entity_type, entity_id) '
        'WHERE content_vector IS NULL';
END
$$;
