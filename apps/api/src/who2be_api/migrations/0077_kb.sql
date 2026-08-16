-- Migration 0077 — Knowledge Base: `kb_node`, `kb_edge`, `kb_edge_evidence`,
-- `kb_node_source_area`, `kb_conflict` (ADR-0047)
-- Plan: .claude/plan/2026-08-13-1200_agent-workarea-knowledge-base.md
--
-- Kuratierte Aussagen (`kb_node`) mit getypten, belegpflichtigen Kanten
-- (`kb_edge`). Die fachlichen Invarianten liegen im Service — die DB ist
-- Backstop:
--   * Belegpflicht „min. 1 Evidence pro Seite" prueft der Service in
--     DERSELBEN Transaktion (kein Teilzustand) — deshalb hier kein
--     Zeilen-CHECK ueber Tabellen hinweg.
--   * Anker-Aufloesung (from/to_anchor -> from/to_node_id) macht der Service;
--     die Anchor-Spalten bewahren die eingegebene ADR-0021-Schreibweise.
--   * Tier-Regeln (hypothesis -> derived nur mit zusaetzlicher Quelle anderer
--     Art; derived -> verified per Update immer verboten) leben im Service.
--   * co_occurs_with verlangt die vier co_-Felder (Query, Fallzahl n,
--     Zeitfenster) — der CHECK unten ist der DB-Backstop, das sprechende 422
--     `correlation_underpowered` (mit tatsaechlichem n) liefert der Service;
--     n >= 20 haelt unterpowerte Korrelationen aus der KB.
--
-- P1-Vorbau auf `kb_node`: `ttl_expires_at`/`status` (Nightly markiert
-- 'stale', loescht nicht) und `derivation_depth` (Ableitungstiefe ab Quelle).
-- `kb_node_source_area` materialisiert die Quell-Areas eines Nodes
-- (Sichtbarkeit: Agent muss ALLE Quell-Areas lesen duerfen; bei
-- derived_from-Kanten monoton ge-UNION-t, Plan-Entscheidung 5).
-- `kb_conflict` sammelt offene Widersprueche (kind 'node': zwei kb_node-IDs,
-- kind 'rule': zwei wa_category_rule-IDs/0078 — polymorph, daher ohne FK).
--
-- FTS wie 0066 ('simple', kein Stemming): Aussagen sind kurz und ggf.
-- gemischtsprachig; der Timeline-Index folgt dem 0074-Muster.
--
-- Idempotenz: CREATE via IF NOT EXISTS; Policy via DROP IF EXISTS + CREATE;
-- GRANT idempotent; pg_roles-Guard schuetzt On-Prem/Dev ohne who2be_app
-- (Muster aus 0066/0070).

CREATE TABLE IF NOT EXISTS kb_node (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id       uuid NOT NULL,
    -- Vertrauensstufe der Aussage (Uebergaenge: Service, s. Kopfkommentar).
    tier               text NOT NULL
                       CHECK (tier IN ('verified', 'derived', 'hypothesis')),
    -- Die Aussage selbst (kuratiert, kurz).
    content            text NOT NULL,
    -- Optionaler Herkunfts-Anker (<artifact_id>#<block_id>, ADR-0021).
    content_ref        text,
    -- Pflicht-Herkunft: sha256:<h> | url:<u> | artifact:<uuid>[#block].
    source_ref         text NOT NULL,
    source_ref_kind    text NOT NULL
                       CHECK (source_ref_kind IN ('blob', 'url', 'artifact')),
    -- P1-Vorbau: TTL/Staleness (Nightly markiert stale, loescht nicht).
    ttl_expires_at     timestamptz,
    status             text NOT NULL DEFAULT 'live'
                       CHECK (status IN ('live', 'stale')),
    derivation_depth   integer NOT NULL DEFAULT 0,
    sensitivity        text NOT NULL DEFAULT 'general'
                       CHECK (sensitivity IN ('general', 'sensitive')),
    -- Fachlicher Zeitpunkt — Pflicht-Input wie bei wa_artifact (0074).
    occurred_at        timestamptz NOT NULL,
    occurred_precision text NOT NULL
                       CHECK (occurred_precision IN ('day', 'minute', 'unknown')),
    created_by         uuid NOT NULL,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    -- FTS ueber die Aussage ('simple': kein Stemming, s. Kopfkommentar).
    search             tsvector GENERATED ALWAYS AS (
                           to_tsvector('simple', content)
                       ) STORED
);

CREATE INDEX IF NOT EXISTS kb_node_workspace_id_idx
    ON kb_node (workspace_id);

CREATE INDEX IF NOT EXISTS kb_node_search_idx
    ON kb_node USING gin (search);

-- Timeline-Pfad (N): nur fachlich datierte Nodes (Muster 0074).
CREATE INDEX IF NOT EXISTS kb_node_timeline_idx
    ON kb_node (workspace_id, occurred_at)
    WHERE occurred_precision <> 'unknown';

CREATE TABLE IF NOT EXISTS kb_edge (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL,
    type         text NOT NULL CHECK (type IN (
                     'supports', 'contradicts', 'supersedes',
                     'derived_from', 'belongs_to', 'co_occurs_with')),
    -- Eingegebene Anker (ADR-0021-Schreibweise); Node-Aufloesung: Service.
    from_anchor  text NOT NULL,
    to_anchor    text NOT NULL,
    from_node_id uuid REFERENCES kb_node (id) ON DELETE CASCADE,
    to_node_id   uuid REFERENCES kb_node (id) ON DELETE CASCADE,
    -- Korrelations-Metadaten, NUR fuer co_occurs_with (Anforderung O):
    -- Abfrage, Fallzahl und Zeitfenster der Korrelation.
    co_query     text,
    co_n         integer,
    co_from      timestamptz,
    co_to        timestamptz,
    created_by   uuid NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    -- DB-Backstop; das sprechende 422 (mit tatsaechlichem n) liefert der
    -- Service (correlation_underpowered).
    CHECK (type <> 'co_occurs_with'
           OR (co_query IS NOT NULL AND co_n IS NOT NULL
               AND co_from IS NOT NULL AND co_to IS NOT NULL)),
    CHECK (co_n IS NULL OR co_n >= 20)
);

CREATE INDEX IF NOT EXISTS kb_edge_workspace_id_idx
    ON kb_edge (workspace_id);

-- Nachbarschafts-Traversierung (neighbors) in beide Richtungen.
CREATE INDEX IF NOT EXISTS kb_edge_from_node_idx
    ON kb_edge (from_node_id);

CREATE INDEX IF NOT EXISTS kb_edge_to_node_idx
    ON kb_edge (to_node_id);

CREATE TABLE IF NOT EXISTS kb_edge_evidence (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL,
    edge_id      uuid NOT NULL REFERENCES kb_edge (id) ON DELETE CASCADE,
    side         text NOT NULL CHECK (side IN ('from', 'to')),
    anchor       text NOT NULL
);

CREATE INDEX IF NOT EXISTS kb_edge_evidence_edge_id_idx
    ON kb_edge_evidence (edge_id);

CREATE INDEX IF NOT EXISTS kb_edge_evidence_workspace_id_idx
    ON kb_edge_evidence (workspace_id);

CREATE TABLE IF NOT EXISTS kb_node_source_area (
    workspace_id uuid NOT NULL,
    node_id      uuid NOT NULL REFERENCES kb_node (id) ON DELETE CASCADE,
    area_id      uuid NOT NULL REFERENCES work_area (id) ON DELETE CASCADE,
    PRIMARY KEY (node_id, area_id)
);

-- Sichtbarkeits-Filter joint pro Area (NOT-EXISTS in der SQL-WHERE).
CREATE INDEX IF NOT EXISTS kb_node_source_area_area_id_idx
    ON kb_node_source_area (area_id);

CREATE INDEX IF NOT EXISTS kb_node_source_area_workspace_id_idx
    ON kb_node_source_area (workspace_id);

CREATE TABLE IF NOT EXISTS kb_conflict (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL,
    kind         text NOT NULL CHECK (kind IN ('node', 'rule')),
    -- Konfliktpartner: kb_node-IDs (kind 'node') bzw. wa_category_rule-IDs
    -- (kind 'rule', 0078) — polymorph, daher bewusst ohne FK.
    a_id         uuid NOT NULL,
    b_id         uuid NOT NULL,
    reason       text NOT NULL,
    opened_at    timestamptz NOT NULL DEFAULT now(),
    resolved_at  timestamptz,
    resolution   text
);

-- Triage-Pfad: offene Konflikte je Workspace.
CREATE INDEX IF NOT EXISTS kb_conflict_open_idx
    ON kb_conflict (workspace_id) WHERE resolved_at IS NULL;

-- RLS strikt auf app.current_tenant (Workspace-Isolation, Muster 0066/0070).
DO $$
DECLARE
    tname text;
BEGIN
    FOREACH tname IN ARRAY ARRAY['kb_node', 'kb_edge', 'kb_edge_evidence',
                                 'kb_node_source_area', 'kb_conflict']
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tname);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', tname);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON %I '
            'USING (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid) '
            'WITH CHECK (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid)',
            tname, 'app.current_tenant', '', 'app.current_tenant', ''
        );
    END LOOP;
END
$$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON kb_node, kb_edge,
            kb_edge_evidence, kb_node_source_area, kb_conflict TO who2be_app;
    END IF;
END
$$;
