-- Migration 0066 — Agent-Memory (ADR-0044)
-- Plan: .claude/plan/2026-07-18-1500_agent-memory.md
--
-- Kuratiertes Langzeitgedaechtnis pro Agent: Agenten schlagen Fakten via MCP
-- `save_memory` vor; je nach `tool_policy.memory_mode` landen sie als
-- 'pending' (suggest — Kurations-Schleuse) oder direkt 'active' (auto). Nur
-- 'active' ist retrieval-sichtbar; 'rejected' bleibt als Dedup-Basis erhalten
-- (verhindert Wieder-Vorschlagen), bis der Mensch endgueltig loescht.
--
-- Namespace: workspace_id (RLS) + agent_id. FK auf agent ON DELETE CASCADE —
-- Memories ohne Agent sind sinnlos (bewusst anders als api_token SET NULL).
-- Kein FK-Verbund zu Versionen: Memory ist KEIN versioniertes Aggregat
-- (leichtgewichtige Zeilen, Hard-Delete-Konvention wie agent_feedback —
-- Abweichung von Kap. 11.6 des Memory-Konzepts, im ADR dokumentiert).
--
-- Retrieval (ADR-0037-Stufe-A-Muster, hier erstmals materialisiert):
-- tsvector-Generated-Column mit 'simple'-Config (Memories sind kurz und
-- gemischtsprachig — Sprach-Stemming wuerde mehr schaden als nutzen) + GIN.
-- pg_trgm-Index auf fact fuer den Dedup-Waechter (similarity) und als
-- Fuzzy-Fallback (Namen/IDs/Abkuerzungen).
--
-- status hat einen CHECK (kleiner, geschlossener Lebenszyklus); category
-- bewusst NICHT (Pydantic-validiert, Konvention wie agent_feedback.signal).
--
-- Idempotenz: CREATE via IF NOT EXISTS; Policy via DROP IF EXISTS + CREATE;
-- GRANT idempotent; pg_roles-Guard schuetzt On-Prem/Dev ohne who2be_app.

-- pg_trgm kann je nach Umgebung in unterschiedlichen Schemata liegen
-- (lokal: public; Supabase: extensions; isolierte Test-Schemata: eigenes) —
-- der Trigram-Index unten qualifiziert die Opklasse daher DYNAMISCH ueber
-- das reale Extension-Schema statt unqualifiziert via search_path.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS agent_memory (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id      uuid NOT NULL,
    agent_id          uuid NOT NULL REFERENCES agent(id) ON DELETE CASCADE,
    -- pending | active | rejected (Kurations-Schleuse, ADR-0044).
    status            text NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending', 'active', 'rejected')),
    fact              text NOT NULL CHECK (char_length(fact) <= 300),
    -- Triage-Hilfe des Agenten (1 Satz Herkunft) — nur UI, nie Retrieval.
    context           text CHECK (char_length(context) <= 200),
    -- preference | fact | project | instruction | entity | general.
    category          text NOT NULL DEFAULT 'general',
    importance        smallint NOT NULL DEFAULT 5
                      CHECK (importance BETWEEN 1 AND 10),
    -- Herkunft: 'agent' (v1); reserviert fuer 'human'/'backfill'.
    source            text NOT NULL DEFAULT 'agent',
    -- Begruendung der Triage-Entscheidung (v. a. bei Ablehnung).
    triage_note       text,
    -- Nutzungs-Log (Transparenz): wie oft/zuletzt in einer Retrieval-Antwort.
    retrieval_count   integer NOT NULL DEFAULT 0,
    last_retrieved_at timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    -- FTS ueber den Fakt ('simple': kein Stemming, siehe Kopfkommentar).
    search            tsvector GENERATED ALWAYS AS (to_tsvector('simple', fact)) STORED
);

CREATE INDEX IF NOT EXISTS agent_memory_scope_idx
    ON agent_memory (workspace_id, agent_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS agent_memory_search_idx
    ON agent_memory USING gin (search);

DO $$
DECLARE
    ext_schema text;
BEGIN
    SELECT n.nspname INTO ext_schema
    FROM pg_extension e
    JOIN pg_namespace n ON n.oid = e.extnamespace
    WHERE e.extname = 'pg_trgm';
    EXECUTE format(
        'CREATE INDEX IF NOT EXISTS agent_memory_fact_trgm_idx '
        'ON agent_memory USING gin (fact %I.gin_trgm_ops)',
        ext_schema
    );
END
$$;

-- RLS strikt auf app.current_tenant (Workspace-Isolation, Muster 0037/0053).
DO $$
BEGIN
    EXECUTE 'ALTER TABLE agent_memory ENABLE ROW LEVEL SECURITY';
    EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON agent_memory';
    EXECUTE format(
        'CREATE POLICY tenant_isolation ON agent_memory '
        'USING (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid) '
        'WITH CHECK (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid)',
        'app.current_tenant', '', 'app.current_tenant', ''
    );
END
$$;

-- Anders als die append-only Telemetrie (0053) braucht Memory UPDATE (Triage,
-- Edit, Nutzungs-Log) und DELETE (Hard-Delete durch den Menschen, DSGVO).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON agent_memory TO who2be_app;
    END IF;
END
$$;
