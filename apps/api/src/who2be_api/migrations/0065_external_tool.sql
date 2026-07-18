-- Migration 0065 — external_tool + external_tool_version (WP-1, Blueprint
-- `.claude/plan/2026-07-18-1315_external-tools-tool-ref.md`)
--
-- Externe MCP-Server/Tool-Bindings als eigenes versioniertes Aggregat, Aufbau
-- 1:1 analog `resource`/`resource_version` (0015 + Folge-Migrationen), aber
-- bereits im finalen, heutigen Zielschema angelegt statt inkrementell
-- nachgezogen (workspace_id direkt auf `resource`, `is_managed` +
-- `managed_content_version` direkt vorhanden, `locale` direkt vorhanden,
-- Status-Default 'draft', RLS + Grants sofort gesetzt):
--   * `alias` lebt auf der Aggregat-Zeile (stabile Identitaet ueber Versionen
--     hinweg, wie der Resource-`slug`/0064 bzw. Template-Slug/0022) — NICHT im
--     Versions-Content, ein Re-Binding darf `tool-ref`-Referenzen nicht brechen.
--   * partieller UNIQUE-Index `(workspace_id, alias)`.
--   * `external_tool_version.workspace_id` wird — wie bei den vier
--     Geschwister-Tabellen (0035) — per Auto-Fill-Trigger aus der
--     Identitaets-Zeile abgeleitet (die generische
--     `VersionedAggregateRepository`-INSERT setzt die Spalte nicht selbst).
--   * `status_history.entity_type`-CHECK-Constraint wird um `'external_tool'`
--     erweitert (Muster 0022).
--
-- Idempotenz: CREATE TABLE/INDEX IF NOT EXISTS, DROP CONSTRAINT IF EXISTS vor
-- ADD CONSTRAINT, Rollen-/Trigger-Guards ueber IF EXISTS/OR REPLACE. Jede
-- Migration laeuft in eigener Transaktion (Runner).

CREATE TABLE IF NOT EXISTS external_tool (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id            uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    owner_id                uuid NOT NULL,
    name                    text NOT NULL,
    alias                   text NOT NULL,
    current_version         int NOT NULL DEFAULT 1,
    is_managed              boolean NOT NULL DEFAULT false,
    managed_content_version int NOT NULL DEFAULT 0,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, id)
);

CREATE INDEX IF NOT EXISTS external_tool_workspace_id_idx
    ON external_tool (workspace_id);

-- Partieller UNIQUE-Index (Blueprint-Wortlaut): `alias` ist heute immer
-- gesetzt (NOT NULL), das `WHERE`-Praedikat haelt die Definition dennoch
-- explizit robust gegen eine kuenftige Lockerung der NOT-NULL-Constraint.
CREATE UNIQUE INDEX IF NOT EXISTS external_tool_workspace_alias_uniq
    ON external_tool (workspace_id, alias) WHERE alias IS NOT NULL;

CREATE TABLE IF NOT EXISTS external_tool_version (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_tool_id uuid NOT NULL REFERENCES external_tool (id) ON DELETE CASCADE,
    version          int NOT NULL,
    content          jsonb NOT NULL,
    status           text NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'review', 'active', 'inactive')),
    locale           text NOT NULL DEFAULT 'de',
    -- Denormalisiert fuer RLS (Trigger unten fuellt sie aus der Identitaets-
    -- Zeile, spiegelt persona_version/playbook_version/resource_version/
    -- system_prompt_template_version aus 0035).
    workspace_id     uuid,
    created_by       uuid NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (external_tool_id, locale, version)
);

-- DB-erzwungene Invariante "max. 1 Draft / 1 Review / 1 Active je (Tool, Sprache)"
-- (analog 0011/0015/0022, bereits im per-locale-Schema aus 0042).
CREATE UNIQUE INDEX IF NOT EXISTS external_tool_version_active_uniq
    ON external_tool_version (external_tool_id, locale) WHERE status = 'active';
CREATE UNIQUE INDEX IF NOT EXISTS external_tool_version_draft_uniq
    ON external_tool_version (external_tool_id, locale) WHERE status = 'draft';
CREATE UNIQUE INDEX IF NOT EXISTS external_tool_version_review_uniq
    ON external_tool_version (external_tool_id, locale) WHERE status = 'review';

CREATE INDEX IF NOT EXISTS external_tool_version_workspace_id_idx
    ON external_tool_version (workspace_id);
CREATE INDEX IF NOT EXISTS external_tool_version_locale_idx
    ON external_tool_version (external_tool_id, locale, version DESC);

-- Composite-FK: workspace_id der Version folgt der Identitaets-Zeile (CASCADE),
-- zusaetzlich an workspace gepinnt — erzwingt, dass die denormalisierte Spalte
-- nie vom Parent abweicht (0035-Muster).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = (current_schema() || '.external_tool_version')::regclass
          AND conname = 'external_tool_version_ws_parent_fkey'
    ) THEN
        ALTER TABLE external_tool_version
            ADD CONSTRAINT external_tool_version_ws_parent_fkey
            FOREIGN KEY (workspace_id, external_tool_id)
            REFERENCES external_tool (workspace_id, id) ON DELETE CASCADE;
    END IF;
END
$$;

-- workspace_id NOT NULL erst NACH dem Composite-FK-Setup (die Spalte muss beim
-- allerersten INSERT ueber den Trigger unten befuellt werden koennen, bevor
-- die Constraint greift — analog 0035, dort per ADD-COLUMN-Reihenfolge geloest,
-- hier per expliziter Trigger-Definition VOR dem SET NOT NULL).
CREATE OR REPLACE FUNCTION w2b_fill_version_workspace_id() RETURNS trigger
LANGUAGE plpgsql AS $fn$
DECLARE
    ws uuid;
BEGIN
    EXECUTE format('SELECT workspace_id FROM %I WHERE id = $1', TG_ARGV[0])
        INTO ws
        USING ((to_jsonb(NEW) ->> TG_ARGV[1])::uuid);
    NEW.workspace_id := ws;
    RETURN NEW;
END;
$fn$;

DROP TRIGGER IF EXISTS external_tool_version_fill_ws ON external_tool_version;
CREATE TRIGGER external_tool_version_fill_ws
    BEFORE INSERT OR UPDATE ON external_tool_version
    FOR EACH ROW EXECUTE FUNCTION w2b_fill_version_workspace_id('external_tool', 'external_tool_id');

ALTER TABLE external_tool_version ALTER COLUMN workspace_id SET NOT NULL;

-- status_history.entity_type um 'external_tool' erweitern (Muster 0022).
ALTER TABLE status_history
    DROP CONSTRAINT IF EXISTS status_history_entity_type_check;
ALTER TABLE status_history
    ADD CONSTRAINT status_history_entity_type_check
    CHECK (entity_type IN ('persona', 'playbook', 'resource',
                           'system_prompt_template', 'external_tool'));

-- Row Level Security (Muster 0037): workspace-scoped, STRIKT auf
-- app.current_tenant. ENABLE (nicht FORCE) — der Tabellen-Owner (Migrations-/
-- On-Prem-Rolle) umgeht RLS weiterhin, nur `who2be_app` (NOBYPASSRLS) wird
-- gefiltert.
DO $$
DECLARE
    tname text;
BEGIN
    FOREACH tname IN ARRAY ARRAY['external_tool', 'external_tool_version']
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

-- Grants fuer die App-Rolle `who2be_app` (Muster 0036).
GRANT SELECT, INSERT, UPDATE, DELETE ON external_tool, external_tool_version
    TO who2be_app;
