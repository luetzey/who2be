-- Migration 0078 — Tabellen-Katalog: `wa_table`, `wa_category_rule`,
-- `wa_source_convention` (ADR-0049)
-- Plan: .claude/plan/2026-08-13-1200_agent-workarea-knowledge-base.md
--
-- Postgres-Katalog des Tabellen-Stores (ADR-0049): die DATEN einer Tabelle
-- liegen in SQLite (eine Datei pro Area, `WHO2BE_TABLESTORE_DIR`), Postgres
-- traegt nur den Katalog. `schema_json` ist das validierte `TableSchema`
-- (`who2be_models/tables.py`: Spalten-/Typen-Allowlist, dedupe_columns,
-- match_column, category_column) — Spaltennamen sind dort auf SQL-sichere
-- Identifier (`^[a-z][a-z0-9_]*$`) beschraenkt, weil sie in SQLite-DDL
-- eingehen. Namens-Adressierung pro Area: UNIQUE (area_id, name).
--
-- `wa_category_rule`: Kategorisierungs-Regeln (Anforderung L, „Regel VOR
-- Modell"). `created_by` ist die Akteur-Kennung als Text
-- (``agent:<id>`` | ``user:<id>`` | ``model:<id>``) — Modelle sind keine
-- DB-Identitaet, daher bewusst KEIN uuid. Zwei aktive Regeln, die dieselbe
-- Row verschieden kategorisieren, werden zum `kb_conflict(kind='rule')`
-- (0077), nie still aufgeloest. UNIQUE (area_id, pattern) macht Upserts
-- deterministisch.
--
-- `wa_source_convention`: Quell-Konventionen (Anforderung M2 — Einheiten,
-- Notation, Dezimal-/Datumsformat als jsonb). Ein `insert_rows` mit
-- `source_name` OHNE Konvention wird abgelehnt (422 convention_missing),
-- nie geraten. `created_by` ist hier ein Mensch (uuid, NULL = System).
--
-- Idempotenz: CREATE via IF NOT EXISTS; Policy via DROP IF EXISTS + CREATE;
-- GRANT idempotent; pg_roles-Guard schuetzt On-Prem/Dev ohne who2be_app
-- (Muster aus 0066/0070).

CREATE TABLE IF NOT EXISTS wa_table (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL,
    area_id      uuid NOT NULL REFERENCES work_area (id) ON DELETE CASCADE,
    name         text NOT NULL,
    -- Validiertes TableSchema (who2be_models/tables.py) — die SQLite-Datei
    -- traegt nur Daten, das Schema lebt hier (ADR-0049).
    schema_json  jsonb NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    -- Tabellen werden pro Area ueber den Namen adressiert.
    UNIQUE (area_id, name)
);

-- List-/Scope-Pfad: Tabellen einer Area im Workspace (Muster 0074).
CREATE INDEX IF NOT EXISTS wa_table_area_idx
    ON wa_table (workspace_id, area_id);

CREATE TABLE IF NOT EXISTS wa_category_rule (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL,
    area_id      uuid NOT NULL REFERENCES work_area (id) ON DELETE CASCADE,
    pattern      text NOT NULL,
    category     text NOT NULL,
    -- Akteur-Kennung als Text: 'agent:<id>' | 'user:<id>' | 'model:<id>'.
    created_by   text NOT NULL,
    -- Optionale Modell-Konfidenz der Regel (nur bei created_by='model:…').
    confidence   numeric CHECK (confidence >= 0 AND confidence <= 1),
    active       boolean NOT NULL DEFAULT true,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    -- Ein Pattern existiert pro Area genau einmal (deterministischer Upsert).
    UNIQUE (area_id, pattern)
);

CREATE INDEX IF NOT EXISTS wa_category_rule_area_idx
    ON wa_category_rule (workspace_id, area_id);

CREATE TABLE IF NOT EXISTS wa_source_convention (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL,
    area_id      uuid NOT NULL REFERENCES work_area (id) ON DELETE CASCADE,
    source_name  text NOT NULL,
    -- Einheiten, Notation, Dezimal-/Datumsformat der Quelle (M2).
    convention   jsonb NOT NULL,
    -- Mensch, der die Konvention gesetzt hat (NULL = System-Seed).
    created_by   uuid,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    -- Genau eine Konvention je (Area, Quelle).
    UNIQUE (area_id, source_name)
);

CREATE INDEX IF NOT EXISTS wa_source_convention_area_idx
    ON wa_source_convention (workspace_id, area_id);

-- RLS strikt auf app.current_tenant (Workspace-Isolation, Muster 0066/0070).
DO $$
DECLARE
    tname text;
BEGIN
    FOREACH tname IN ARRAY ARRAY['wa_table', 'wa_category_rule',
                                 'wa_source_convention']
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
        GRANT SELECT, INSERT, UPDATE, DELETE ON wa_table, wa_category_rule,
            wa_source_convention TO who2be_app;
    END IF;
END
$$;
