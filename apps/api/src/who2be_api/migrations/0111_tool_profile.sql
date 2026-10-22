-- Migration 0111 — Werkzeug-Profile pro Agent: `tool_profile` und drei
-- Spalten an `agent` (ADR-0059 §4, Paket Q2a).
--
-- Nummer: Die ADR nennt 0110 (PM-Vergabe). 0110 ist inzwischen von
-- `0110_account_state.sql` (#1031) belegt, 0109 ist fuer Rechnung R2
-- reserviert (ADR-0061). Deshalb 0111, geprueft gegen origin/main und alle
-- Remote-Branches.
--
-- Ein Profil ist KEIN Recht (ADR-0059 §3.3): es blendet nur Werkzeuge aus, die
-- Rechte (`agent.tool_policy`) bleiben unberuehrt. Deshalb eigene Spalten statt
-- eines Felds in `tool_policy`. Dazu kommt: der Start-Abgleich der verwalteten
-- Builder-Inhalte (`sync_managed_builder_content`) ersetzt `tool_policy` ganz
-- und wuerde eine Profil-Anpassung durch einen Menschen wieder ueberschreiben.
--
-- „Alle“ ist kein gespeichertes Profil, sondern `agent.tool_profile_id IS NULL`.
-- Die Standardwerte der drei Spalten bedeuten „Alle ohne Ausnahmen“. Bestehende
-- Agenten bleiben damit unveraendert (Owner d). Die einzige Ausnahme sind die
-- verwalteten Builder-Agenten (W59-3 = A, Schritt 4).
--
-- Doppelschicht, Muster 0047/0060: Der Seed der vier mitgelieferten Profile
-- (Schritt 3) spiegelt `BUILTIN_PROFILES` in
-- `packages/models/src/who2be_models/tool_profiles.py`, die einzige Quelle. Neue
-- Workspaces seedet `repositories/tool_profile_repository.py#seed_builtin_profiles`
-- aus dem Modul. Die SQL-Datei kann das Modul nicht importieren. Der
-- Paritaetstest `test_tool_profile_repository.py` vergleicht beide Wege
-- (Namen, Gruppen, Werkzeuge, Builder-Zuordnung).
--
-- Fremdschluessel agent -> tool_profile: zusammengesetzt ueber
-- (workspace_id, tool_profile_id), damit das Profil im Workspace des Agenten
-- liegt. Ist tool_profile_id NULL, prueft Postgres ihn nicht (MATCH SIMPLE).
-- ON DELETE RESTRICT: ein Profil, das noch an Agenten haengt, laesst sich nicht
-- loeschen (API: 409 `tool_profile_in_use`). Beim Workspace- und Org-Loeschen
-- faellt `tool_profile` per CASCADE mit.
--
-- Kein `created_by`: wer ein Profil anlegt oder aendert, steht im `audit_log`
-- (ADR-0059 §7.4). Die Tabelle traegt damit keine personenbezogenen Daten.
--
-- Rueckweg (als eigene Vorwaerts-Migration): Constraint
-- `agent_tool_profile_fk` und die drei Agent-Spalten droppen, dann die Tabelle.
--
-- Idempotenz: CREATE ... IF NOT EXISTS, ADD COLUMN IF NOT EXISTS, Constraint
-- per pg_constraint-Guard, Policy per DROP IF EXISTS + CREATE, Seed per
-- ON CONFLICT DO NOTHING, Zuordnung nur bei `tool_profile_id IS NULL`. Der
-- pg_roles-Guard deckt On-Prem/Dev ohne `who2be_app` ab.

-- --- 1. Tabelle ---------------------------------------------------------------

CREATE TABLE IF NOT EXISTS tool_profile (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id  uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    builtin_key   text NULL
        CONSTRAINT tool_profile_builtin_key_check
        CHECK (builtin_key IN ('read', 'author', 'curator', 'builder')),
    name          text NOT NULL
        CONSTRAINT tool_profile_name_check CHECK (length(name) BETWEEN 1 AND 80),
    description   text NOT NULL DEFAULT '',
    groups        text[] NOT NULL DEFAULT '{}',
    tools         text[] NOT NULL DEFAULT '{}',
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT tool_profile_workspace_id_id_key UNIQUE (workspace_id, id),
    CONSTRAINT tool_profile_workspace_builtin_key UNIQUE (workspace_id, builtin_key)
);

CREATE UNIQUE INDEX IF NOT EXISTS tool_profile_name_uq
    ON tool_profile (workspace_id, lower(name));

-- --- 2. Zuordnung am Agenten --------------------------------------------------

ALTER TABLE agent
    ADD COLUMN IF NOT EXISTS tool_profile_id uuid NULL,
    ADD COLUMN IF NOT EXISTS tools_added     text[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS tools_removed   text[] NOT NULL DEFAULT '{}';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'agent_tool_profile_fk'
          AND conrelid = 'agent'::regclass
    ) THEN
        ALTER TABLE agent
            ADD CONSTRAINT agent_tool_profile_fk
            FOREIGN KEY (workspace_id, tool_profile_id)
            REFERENCES tool_profile (workspace_id, id) ON DELETE RESTRICT;
    END IF;
END
$$;

-- Fuer die Zaehlung „Agenten je Profil“ und die RESTRICT-Pruefung.
CREATE INDEX IF NOT EXISTS agent_tool_profile_idx
    ON agent (workspace_id, tool_profile_id)
    WHERE tool_profile_id IS NOT NULL;

-- --- 3. Seed: vier mitgelieferte Profile je Bestands-Workspace ----------------
-- Spiegel von `BUILTIN_PROFILES` (who2be_models/tool_profiles.py). Namen nach
-- `workspace.content_locale`; jede andere Sprache als 'en' bekommt die
-- deutschen Namen (DEFAULT_LOCALE, wie im Code).

INSERT INTO tool_profile (workspace_id, builtin_key, name, groups)
SELECT w.id,
       p.builtin_key,
       CASE WHEN w.content_locale = 'en' THEN p.name_en ELSE p.name_de END,
       p.groups
FROM workspace w
CROSS JOIN (
    VALUES
        ('read', 'Lesen', 'Read',
         ARRAY['core', 'read', 'feedback_memory', 'workarea_read']::text[]),
        ('author', 'Autor', 'Author',
         ARRAY['core', 'read', 'feedback_memory', 'workarea_read',
               'content_write', 'transition', 'workarea_write']::text[]),
        ('curator', 'Kurator', 'Curator',
         ARRAY['core', 'read', 'feedback_memory', 'workarea_read',
               'transition', 'curation']::text[]),
        -- W59-4 (Owner 2026-10-21): „Builder“ enthaelt `workarea_read`.
        ('builder', 'Builder', 'Builder',
         ARRAY['core', 'read', 'feedback_memory', 'workarea_read',
               'content_write', 'transition', 'agent_admin', 'system_prompt',
               'curation']::text[])
) AS p (builtin_key, name_de, name_en, groups)
ON CONFLICT (workspace_id, builtin_key) DO NOTHING;

-- --- 4. Verwaltete Builder-Agenten auf „Builder“ (W59-3 = A) ------------------
-- Builder und Builder-Lite (`is_managed = true`). Ein Mensch kann danach auf
-- „Alle“ zurueckstellen (ADR-0059 §7.3).

UPDATE agent a
SET tool_profile_id = p.id
FROM tool_profile p
WHERE p.workspace_id = a.workspace_id
  AND p.builtin_key = 'builder'
  AND a.is_managed = true
  AND a.tool_profile_id IS NULL;

-- --- 5. RLS -------------------------------------------------------------------
-- Strikt auf app.current_tenant (Workspace-Isolation, Muster 0100).

DO $$
BEGIN
    EXECUTE 'ALTER TABLE tool_profile ENABLE ROW LEVEL SECURITY';
    EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON tool_profile';
    EXECUTE format(
        'CREATE POLICY tenant_isolation ON tool_profile '
        'USING (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid) '
        'WITH CHECK (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid)',
        'app.current_tenant', '', 'app.current_tenant', ''
    );
END
$$;

-- --- 6. Grants ----------------------------------------------------------------
-- Profile sind pflegbar (UPDATE) und eigene loeschbar (DELETE). Die neuen
-- Agent-Spalten deckt der Tabellen-Grant aus 0036 ab.

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON tool_profile TO who2be_app;
    END IF;
END
$$;
