-- Migration 0103 — Gespraechsprotokoll und Massnahme: `feedback_session`,
-- `feedback_session_case`, `measure`, `measure_case`, `measure_event`
-- (ADR-0053 Abschnitte 3.5, 3.6; Lernschleife Phase E, Paket E2a-1)
--
-- Das Gespraech findet im Client statt; Who2Be speichert das Ergebnis. Ein
-- Protokoll wird in EINEM Aufruf samt Faellen und Massnahmen eingereicht und
-- ist danach unveraenderlich (3.5) — ueber die Grants, nicht ueber einen
-- Status. Eine Korrektur ist ein neues Protokoll mit `supersedes_id`; beide
-- bleiben sichtbar.
--
-- Massnahme: gehoert zu genau einer Sitzung, deckt >= 1 Fall ab (die
-- Mindestzahl prueft der Service, E2b-1) und hat immer einen Pruefall
-- (`test_case_id` NOT NULL, 3.6 „Pflicht“). Ihr Zustand ist keine Spalte,
-- sondern das juengste `measure_event` (Muster `agent_case_event`, 0100). Der
-- Verweis Entwurf <-> Massnahme liegt als Event `draft_linked` an der
-- Massnahme (Weiche E2 = a), keine `*_version`-Tabelle aendert sich.
--
-- Zuordnung zum Agenten (alles per Composite-FK in der Datenbank):
-- - Ein Protokoll bespricht EINEN Agenten (3.5 `agent_id`). Seine Faelle
--   (`feedback_session_case`), seine Massnahmen samt deren Faellen
--   (`measure`, `measure_case`) und der Pruefall jeder Massnahme
--   (`test_case.agent_id`) gehoeren zu diesem Agenten. Dafuer tragen
--   `feedback_session_case`, `measure` und `measure_case` die `agent_id`
--   mit, und `test_case` bekommt das Ziel `UNIQUE (workspace_id, agent_id,
--   id)`.
-- - `supersedes_id` zeigt auf ein Protokoll desselben Agenten.
-- - Dass die Faelle einer Massnahme auch Faelle ihres Protokolls sind, prueft
--   der Service (E2b-1).
--
-- Event-Invarianten als DB-CHECK (3.6, Tabelle der Events; die Reihenfolge
-- der Events prueft der Service):
-- - `draft_linked` und `activated` nur mit Version, alle anderen ohne.
-- - `metrics` (jsonb-Objekt) genau bei `follow_up_prepared`.
-- - `verdict` genau bei `reviewed`.
-- - `reviewed` und `withdrawn` nur durch einen Menschen (F-W7, „Partei, nicht
--   Richter“), `activated` nur durch das System (3.6 „Wer: System“),
--   `follow_up_prepared` nie durch einen Menschen (3.6 „Builder oder System“).
-- - `withdrawn` und `verdict = 'ineffective'` nur mit Begruendung (`note`):
--   `ineffective` setzt die Faelle auf `reopened`, und `reopened` verlangt
--   eine Begruendung (3.3, Uebergangstabelle).
--
-- Unveraenderlichkeit und Loeschen (PM-6, Owner 2026-10-08 fuer Faelle):
-- - Alle fuenf Tabellen: `who2be_app` hat NUR SELECT + INSERT.
-- - Das Loeschen eines Falls (`agent_case`, DELETE ab `editor`, 0100) nimmt
--   per ON DELETE CASCADE nur die Verknuepfungen `feedback_session_case` und
--   `measure_case` mit; Protokoll und Massnahme bleiben. Referenzielle
--   Aktionen brauchen kein DELETE-Recht der App-Rolle (wie die Events in
--   0100).
-- - Agent- und Workspace-Purge (Owner) loeschen alles per CASCADE.
-- - Die Anonymisierung beim Konto-Purge (`submitted_by`, menschliche
--   `participants`-IDs, `actor_id` menschlicher `measure_event`) macht der
--   Owner im Paket E2a-2.
--
-- Bewusst ohne FK:
-- - `measure.entity_id` und `measure_event.version_id` (polymorph, Muster
--   `agent_case_element.entity_id`, `test_run.subject_version_id`; die
--   Zugehoerigkeit prueft der Service).
-- - `agent_case_event.measure_id` (0100) bekommt hier keinen FK: das gehoert
--   nicht zum Umfang dieses Pakets.
--
-- Rueckweg (als eigene Vorwaerts-Migration): die fuenf Tabellen droppen
-- (Event, Massnahme-Fall, Massnahme, Sitzung-Fall, Sitzung) und den
-- Constraint `test_case_workspace_id_agent_id_id_key` droppen.
--
-- Idempotenz: CREATE via IF NOT EXISTS; Constraint auf `test_case` via
-- pg_constraint-Guard; Policy via DROP IF EXISTS + CREATE; GRANT idempotent;
-- pg_roles-Guard schuetzt On-Prem/Dev ohne who2be_app.

-- --- FK-Ziele auf Bestandstabellen -------------------------------------------

-- Pruefall einer Massnahme gehoert demselben Agenten (s. `measure`).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = (current_schema() || '.test_case')::regclass
          AND conname = 'test_case_workspace_id_agent_id_id_key'
    ) THEN
        ALTER TABLE test_case
            ADD CONSTRAINT test_case_workspace_id_agent_id_id_key
            UNIQUE (workspace_id, agent_id, id);
    END IF;
END
$$;

-- --- Gespraechsprotokoll -----------------------------------------------------

CREATE TABLE IF NOT EXISTS feedback_session (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id       uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    -- Der besprochene Agent.
    agent_id           uuid NOT NULL,
    trigger            text NOT NULL CHECK (trigger IN ('threshold', 'scheduled', 'manual')),
    -- Liste `{kind: human|agent|builder, id, role}`; Form im Modell.
    participants       jsonb NOT NULL DEFAULT '[]'::jsonb
                       CHECK (jsonb_typeof(participants) = 'array'),
    summary            text NOT NULL CHECK (char_length(summary) BETWEEN 1 AND 4000),
    -- Liste `{text, standard_ref?}`: entschiedene Widersprueche.
    decisions          jsonb NOT NULL DEFAULT '[]'::jsonb
                       CHECK (jsonb_typeof(decisions) = 'array'),
    -- Liste `{participant_kind, participant_id, text}`; auch der Agent darf.
    dissent            jsonb NOT NULL DEFAULT '[]'::jsonb
                       CHECK (jsonb_typeof(dissent) = 'array'),
    follow_up_at       date NOT NULL,
    -- Das Protokoll, das dieses hier korrigiert (3.5).
    supersedes_id      uuid,
    submitted_by_kind  text NOT NULL CHECK (submitted_by_kind IN ('human', 'agent')),
    -- Mensch: Nutzer-ID; Agent: Agent-ID. Polymorph, ohne FK.
    submitted_by       uuid NOT NULL,
    created_at         timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (workspace_id, id),
    -- Ziel fuer Faelle und Korrekturen desselben Agenten.
    UNIQUE (workspace_id, agent_id, id),
    CONSTRAINT feedback_session_supersedes_self_check
        CHECK (supersedes_id IS NULL OR supersedes_id <> id),
    CONSTRAINT feedback_session_agent_fkey
        FOREIGN KEY (workspace_id, agent_id)
        REFERENCES agent (workspace_id, id) ON DELETE CASCADE,
    CONSTRAINT feedback_session_supersedes_fkey
        FOREIGN KEY (workspace_id, agent_id, supersedes_id)
        REFERENCES feedback_session (workspace_id, agent_id, id)
        ON DELETE SET NULL (supersedes_id)
);

-- Liste je Workspace und je Agent, neueste zuerst (Keyset auf created_at, id).
CREATE INDEX IF NOT EXISTS feedback_session_workspace_created_idx
    ON feedback_session (workspace_id, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS feedback_session_agent_created_idx
    ON feedback_session (workspace_id, agent_id, created_at DESC, id DESC);
-- Korrekturkette (`superseded_by`) und FK-Index fuer ON DELETE SET NULL.
CREATE INDEX IF NOT EXISTS feedback_session_supersedes_idx
    ON feedback_session (workspace_id, supersedes_id) WHERE supersedes_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS feedback_session_case (
    workspace_id  uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    session_id    uuid NOT NULL,
    agent_id      uuid NOT NULL,
    case_id       uuid NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (workspace_id, session_id, case_id),
    CONSTRAINT feedback_session_case_session_fkey
        FOREIGN KEY (workspace_id, agent_id, session_id)
        REFERENCES feedback_session (workspace_id, agent_id, id) ON DELETE CASCADE,
    -- PM-6: Fall weg -> nur die Verknuepfung geht.
    CONSTRAINT feedback_session_case_case_fkey
        FOREIGN KEY (workspace_id, agent_id, case_id)
        REFERENCES agent_case (workspace_id, agent_id, id) ON DELETE CASCADE
);

-- „Protokolle zu einem Fall“ (QE1) und FK-Index fuer die Fall-Cascade.
CREATE INDEX IF NOT EXISTS feedback_session_case_case_idx
    ON feedback_session_case (workspace_id, case_id);

-- --- Massnahme ---------------------------------------------------------------

CREATE TABLE IF NOT EXISTS measure (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id       uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    -- Der Agent des Protokolls (denormalisiert, nur fuer die Composite-FKs).
    agent_id           uuid NOT NULL,
    session_id         uuid NOT NULL,
    -- Werte wie `agent_case_element.target`, ausser `model_limit` (3.6).
    target             text NOT NULL CHECK (target IN (
                           'persona', 'playbook', 'resource', 'external_tool',
                           'system_prompt_template', 'tool_policy', 'memory')),
    entity_id          uuid,
    change_summary     text NOT NULL CHECK (char_length(change_summary) BETWEEN 1 AND 2000),
    -- Pflicht: der Pruefall aus dem echten Fall (3.6).
    test_case_id       uuid NOT NULL,
    success_criterion  text NOT NULL CHECK (char_length(success_criterion) BETWEEN 1 AND 1000),
    counterposition    text NOT NULL CHECK (char_length(counterposition) BETWEEN 1 AND 1000),
    -- Optional; ohne Wert gilt `feedback_session.follow_up_at`.
    follow_up_at       date,
    created_at         timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (workspace_id, id),
    UNIQUE (workspace_id, agent_id, id),
    -- `entity_id` genau bei `tool_policy` (haengt am Agenten) NULL.
    CONSTRAINT measure_entity_check
        CHECK ((entity_id IS NULL) = (target = 'tool_policy')),
    CONSTRAINT measure_session_fkey
        FOREIGN KEY (workspace_id, agent_id, session_id)
        REFERENCES feedback_session (workspace_id, agent_id, id) ON DELETE CASCADE,
    -- Pruefall desselben Agenten. `who2be_app` kann ihn nicht loeschen
    -- (0089: kein DELETE-Grant); er verschwindet nur mit Agent bzw. Workspace,
    -- und dann geht die Massnahme ohnehin mit. CASCADE statt NO ACTION, weil
    -- Postgres die NO-ACTION-Pruefung beim Agent-Purge vor der Cascade ueber
    -- `feedback_session` ausfuehrt und den Purge sonst abbricht.
    CONSTRAINT measure_test_case_fkey
        FOREIGN KEY (workspace_id, agent_id, test_case_id)
        REFERENCES test_case (workspace_id, agent_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS measure_session_idx
    ON measure (workspace_id, session_id, created_at, id);
CREATE INDEX IF NOT EXISTS measure_test_case_idx
    ON measure (workspace_id, test_case_id);

CREATE TABLE IF NOT EXISTS measure_case (
    workspace_id  uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    measure_id    uuid NOT NULL,
    agent_id      uuid NOT NULL,
    case_id       uuid NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (workspace_id, measure_id, case_id),
    CONSTRAINT measure_case_measure_fkey
        FOREIGN KEY (workspace_id, agent_id, measure_id)
        REFERENCES measure (workspace_id, agent_id, id) ON DELETE CASCADE,
    -- PM-6: Fall weg -> nur die Verknuepfung geht.
    CONSTRAINT measure_case_case_fkey
        FOREIGN KEY (workspace_id, agent_id, case_id)
        REFERENCES agent_case (workspace_id, agent_id, id) ON DELETE CASCADE
);

-- „Massnahmen je Fall“ (E3) und FK-Index fuer die Fall-Cascade.
CREATE INDEX IF NOT EXISTS measure_case_case_idx
    ON measure_case (workspace_id, case_id);

-- --- Ereignisse der Massnahme (append-only) -----------------------------------

CREATE TABLE IF NOT EXISTS measure_event (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id         uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    measure_id           uuid NOT NULL,
    event                text NOT NULL CHECK (event IN (
                             'draft_linked', 'activated', 'follow_up_prepared',
                             'reviewed', 'withdrawn')),
    actor_kind           text NOT NULL CHECK (actor_kind IN ('human', 'agent', 'system')),
    -- Mensch: Nutzer-ID; Agent: Agent-ID; System: NULL. Polymorph, ohne FK.
    actor_id             uuid,
    version_entity_type  text CHECK (version_entity_type IN (
                             'persona', 'playbook', 'resource',
                             'external_tool', 'system_prompt_template')),
    version_id           uuid,
    verdict              text CHECK (verdict IN ('effective', 'ineffective', 'not_measurable')),
    metrics              jsonb CHECK (metrics IS NULL OR jsonb_typeof(metrics) = 'object'),
    note                 text CHECK (char_length(note) BETWEEN 1 AND 2000),
    created_at           timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT measure_event_version_pair_check
        CHECK ((version_entity_type IS NULL) = (version_id IS NULL)),
    CONSTRAINT measure_event_version_check
        CHECK ((event IN ('draft_linked', 'activated')) = (version_id IS NOT NULL)),
    CONSTRAINT measure_event_metrics_event_check
        CHECK ((event = 'follow_up_prepared') = (metrics IS NOT NULL)),
    CONSTRAINT measure_event_verdict_event_check
        CHECK ((event = 'reviewed') = (verdict IS NOT NULL)),
    CONSTRAINT measure_event_reason_check
        CHECK ((event <> 'withdrawn' AND verdict IS DISTINCT FROM 'ineffective')
               OR note IS NOT NULL),
    CONSTRAINT measure_event_human_only_check
        CHECK (event NOT IN ('reviewed', 'withdrawn') OR actor_kind = 'human'),
    CONSTRAINT measure_event_system_only_check
        CHECK (event <> 'activated' OR actor_kind = 'system'),
    CONSTRAINT measure_event_prepared_actor_check
        CHECK (event <> 'follow_up_prepared' OR actor_kind <> 'human'),
    CONSTRAINT measure_event_human_actor_check
        CHECK (actor_kind <> 'human' OR actor_id IS NOT NULL),
    CONSTRAINT measure_event_measure_fkey
        FOREIGN KEY (workspace_id, measure_id)
        REFERENCES measure (workspace_id, id) ON DELETE CASCADE
);

-- Juengstes Event je Massnahme (Zustand) und Verlauf.
CREATE INDEX IF NOT EXISTS measure_event_measure_idx
    ON measure_event (workspace_id, measure_id, created_at DESC, id DESC);
-- „Massnahmen je verknuepfter Version“ (E3: Aktivierung -> `activated`).
CREATE INDEX IF NOT EXISTS measure_event_version_idx
    ON measure_event (workspace_id, version_entity_type, version_id)
    WHERE event = 'draft_linked';

-- --- RLS ---------------------------------------------------------------------

-- Strikt auf app.current_tenant (Workspace-Isolation, Muster 0089/0100).
DO $$
DECLARE
    tbl text;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'feedback_session', 'feedback_session_case', 'measure', 'measure_case',
        'measure_event'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tbl);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', tbl);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON %I '
            'USING (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid) '
            'WITH CHECK (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid)',
            tbl, 'app.current_tenant', '', 'app.current_tenant', ''
        );
    END LOOP;
END
$$;

-- --- Grants ------------------------------------------------------------------

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        -- Unveraenderlich (3.5): weder UPDATE noch DELETE. Die Loeschpfade
        -- nach PM-6 laufen ueber FK-CASCADE bzw. den Owner.
        GRANT SELECT, INSERT ON feedback_session TO who2be_app;
        GRANT SELECT, INSERT ON feedback_session_case TO who2be_app;
        GRANT SELECT, INSERT ON measure TO who2be_app;
        GRANT SELECT, INSERT ON measure_case TO who2be_app;
        GRANT SELECT, INSERT ON measure_event TO who2be_app;
    END IF;
END
$$;
