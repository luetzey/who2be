-- Migration 0100 — Fall: `agent_case`, `agent_case_event`,
-- `agent_case_element`, `agent_case_statement` (ADR-0053 Abschnitte 3.3, 5.2;
-- Lernschleife Phase D, Paket D1a)
--
-- Ein Fall ist die Einzelrueckmeldung zum Verhalten EINES Agenten (SBI plus
-- erwartetes Verhalten). Der Inhalt ist nach dem Anlegen unveraenderlich;
-- alles Weitere sind Events.
--
-- Status: KEINE Spalte. Der Status ist das juengste Status-Event
-- (`reported` = open, sonst der Eventname; Muster `feedback_resolution`,
-- 0054). Das Anlegen schreibt `reported` in derselben Transaktion
-- (Repository). `created_at` der Events, Zuordnungen und Schilderungen kommt
-- aus `clock_timestamp()`, nicht aus `now()`: mehrere Zeilen einer Transaktion
-- bekaemen sonst dieselbe Zeit und die Reihenfolge waere nicht bestimmt.
--
-- Zuordnung `agent_case_element` (n:m): Ziel aus acht Arten; `entity_id` ist
-- genau bei `tool_policy` (haengt am Agenten) und `model_limit` NULL (DB-CHECK).
-- Polymorph, daher ohne FK auf das Element (Muster `test_case.entity_id`, 0089).
-- Loeschen erlaubt (3.3: korrigierbar), das Event `element_unassigned` haelt es
-- fest — dafuer traegt das Event `element_target`/`element_entity_id`.
--
-- Schilderung `agent_case_statement`: nur der betroffene Agent. Der Composite-FK
-- auf `agent_case (workspace_id, id, agent_id)` erzwingt
-- `statement.agent_id = agent_case.agent_id` in der Datenbank.
--
-- Event-Invarianten als DB-CHECK (3.3, Uebergangstabelle; die Pruefung der
-- erlaubten Uebergaenge macht der Service in D2):
-- - `addressed` nur mit Version (`version_entity_type`, `version_id`; F-W6).
-- - `in_progress` und `verified` nur mit `measure_id`.
-- - `reopened` und `dismissed` nur mit Begruendung (`note`).
-- - Ein Agent setzt nie `addressed`, `verified` oder `dismissed` (F-W7,
--   „Partei, nicht Richter“). Massgeblich bleibt die Service-Pruefung ueber
--   `is_agent_bound`; der CHECK ist die letzte Linie.
-- - Element-Events nur mit Element, alle anderen ohne.
--
-- Unveraenderlichkeit (Grants statt Trigger, Muster 0044/0089):
-- - `agent_case`: SELECT, INSERT, DELETE — kein UPDATE. DELETE fuer das
--   Loeschen ab `editor` (PM-Entscheidung Q6, 2026-10-07): Hard-Delete samt
--   Verlauf (Events, Zuordnung, Schilderungen per CASCADE), zurueck bleibt
--   eine inhaltsfreie `audit_log`-Zeile `case.deleted` (Weiche G3/M5, schreibt
--   das Repository).
-- - `agent_case_event`, `agent_case_statement`: append-only, SELECT + INSERT.
-- - `agent_case_element`: SELECT, INSERT, DELETE (3.3).
-- Der Owner (Migrations-/Purge-Job) behaelt Vollzugriff (DSGVO-Erasure).
--
-- Herkunft:
-- - `source_feedback_id`: Alt-Feedback, aus dem ein Mensch den Fall
--   uebernommen hat (Weiche F1 = a, 5.2: das Alt-Feedback bleibt unveraendert).
--   ON DELETE SET NULL, denn Alt-Feedback ist hart loeschbar (0058).
-- - `agent_memory.converted_case_id` (0091 hat den FK bewusst offen gelassen):
--   Composite-FK ueber `(workspace_id, agent_id, …)`. Lernvorschlag und Fall
--   gehoeren damit zwingend zu DEMSELBEN Agenten (ein Lernvorschlag ist die
--   Lehre eines Agenten ueber sich selbst, 3.1.6), und das Loeschen des
--   Agenten raeumt beide in einer Anweisung ab. ON DELETE NO ACTION:
--   SET NULL braeche den CHECK `converted <=> converted_case_id` aus 0091. Einen
--   Fall, aus dem ein Lernvorschlag wurde, loescht man daher erst, nachdem der
--   Vorschlag umgestellt ist (Service, D2). Neuer CHECK
--   `converted_case_id IS NULL OR kind = 'lesson'` (3.1: „nur fuer lesson“);
--   weil `lesson` nie `scope='user'` ist, ist `agent_id` dann gesetzt und der
--   FK greift immer vollstaendig (MATCH SIMPLE prueft sonst nicht).
--   Bestand: kein Schreibpfad setzt bisher `converted_case_id` (nur Tests).
-- - `source_memory_id` ist die Gegenrichtung derselben Beziehung und bewusst
--   OHNE FK (weicher Verweis, Muster `agent_feedback.entity_id`): ein zweiter
--   FK schloesse den Kreis agent_case <-> agent_memory, und der Org-Transfer
--   (`core/org_transfer.py`) braucht eine zyklenfreie Import-Reihenfolge.
--   Massgeblich und durchgesetzt ist `converted_case_id`; ein verwaister
--   Verweis traegt keinen Inhalt (Leser behandeln ihn als „Quelle geloescht“).
--
-- Rueckweg (5.2, als eigene Vorwaerts-Migration — Migrationen sind
-- unveraenderlich): Faelle mit `source_feedback_id` bleiben als Export
-- erhalten; `agent_memory`-Zeilen mit `status='converted'` auf `rejected`
-- und `converted_case_id` auf NULL; FK `agent_memory_converted_case_fkey` und
-- CHECK `agent_memory_converted_lesson_check` droppen; die vier Tabellen
-- droppen (Statement, Element, Event, Fall). `agent_feedback` und
-- `feedback_resolution` bleiben unberuehrt. Das zusaetzliche UNIQUE-Ziel
-- auf `agent_feedback` kann bleiben.
--
-- Idempotenz: CREATE via IF NOT EXISTS; Constraints auf Bestandstabellen via
-- pg_constraint-Guard bzw. DROP IF EXISTS + ADD; Policy via DROP IF EXISTS +
-- CREATE; GRANT idempotent; pg_roles-Guard schuetzt On-Prem/Dev ohne who2be_app.

-- --- FK-Ziele auf Bestandstabellen -------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = (current_schema() || '.agent_feedback')::regclass
          AND conname = 'agent_feedback_workspace_id_id_key'
    ) THEN
        ALTER TABLE agent_feedback
            ADD CONSTRAINT agent_feedback_workspace_id_id_key UNIQUE (workspace_id, id);
    END IF;
END
$$;

-- --- Fall --------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_case (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    -- Der Agent, um dessen Verhalten es geht (Pflicht, F-W1).
    agent_id            uuid NOT NULL,
    reporter_kind       text NOT NULL
                        CHECK (reporter_kind IN ('human', 'agent', 'builder', 'pattern')),
    -- Nutzer aus der Auth-Schicht, ohne FK (Muster `test_run.reported_by_user_id`).
    reporter_user_id    uuid,
    reporter_agent_id   uuid,
    situation           text NOT NULL CHECK (char_length(situation) BETWEEN 1 AND 4000),
    behavior            text NOT NULL CHECK (char_length(behavior) BETWEEN 1 AND 4000),
    impact              text CHECK (char_length(impact) BETWEEN 1 AND 2000),
    expected_behavior   text NOT NULL
                        CHECK (char_length(expected_behavior) BETWEEN 1 AND 2000),
    severity            text NOT NULL DEFAULT 'medium'
                        CHECK (severity IN ('low', 'medium', 'high')),
    -- Schnelle Kategorie, Wertemenge wie `FeedbackSignal`.
    signal              text
                        CHECK (signal IN ('helpful', 'outdated', 'incorrect', 'unclear')),
    source_ref          text CHECK (char_length(source_ref) BETWEEN 1 AND 500),
    source_feedback_id  uuid,
    source_memory_id    uuid,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, id),
    -- Ziel fuer `agent_memory.converted_case_id` (gleicher Agent).
    UNIQUE (workspace_id, agent_id, id),
    -- Ziel fuer die Schilderung (betroffener Agent).
    UNIQUE (workspace_id, id, agent_id),
    -- Ein Mensch meldet nie anonym (Weiche F2: kein anonymer Kanal).
    CONSTRAINT agent_case_human_reporter_check
        CHECK (reporter_kind <> 'human' OR reporter_user_id IS NOT NULL),
    CONSTRAINT agent_case_agent_fkey
        FOREIGN KEY (workspace_id, agent_id)
        REFERENCES agent (workspace_id, id) ON DELETE CASCADE,
    CONSTRAINT agent_case_reporter_agent_fkey
        FOREIGN KEY (workspace_id, reporter_agent_id)
        REFERENCES agent (workspace_id, id) ON DELETE SET NULL (reporter_agent_id),
    CONSTRAINT agent_case_source_feedback_fkey
        FOREIGN KEY (workspace_id, source_feedback_id)
        REFERENCES agent_feedback (workspace_id, id) ON DELETE SET NULL (source_feedback_id)
);

-- Liste je Workspace und je Agent, neueste zuerst (Keyset auf created_at, id).
CREATE INDEX IF NOT EXISTS agent_case_workspace_created_idx
    ON agent_case (workspace_id, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS agent_case_agent_created_idx
    ON agent_case (workspace_id, agent_id, created_at DESC);
-- „Eigene gemeldete Faelle“ (viewer, 3.3 Rechte).
CREATE INDEX IF NOT EXISTS agent_case_reporter_user_idx
    ON agent_case (workspace_id, reporter_user_id)
    WHERE reporter_user_id IS NOT NULL;
-- FK-Indizes fuer ON DELETE SET NULL; `source_memory_id` fuer die Rueckfrage
-- „welcher Fall kam aus diesem Lernvorschlag“.
CREATE INDEX IF NOT EXISTS agent_case_reporter_agent_idx
    ON agent_case (reporter_agent_id) WHERE reporter_agent_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS agent_case_source_feedback_idx
    ON agent_case (source_feedback_id) WHERE source_feedback_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS agent_case_source_memory_idx
    ON agent_case (source_memory_id) WHERE source_memory_id IS NOT NULL;

-- --- Events (append-only) ----------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_case_event (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id         uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    case_id              uuid NOT NULL,
    event                text NOT NULL CHECK (event IN (
                             'reported', 'triaged', 'in_progress', 'addressed',
                             'verified', 'reopened', 'dismissed',
                             'element_assigned', 'element_unassigned', 'statement')),
    actor_kind           text NOT NULL CHECK (actor_kind IN ('human', 'agent', 'system')),
    -- Mensch: Nutzer-ID; Agent: Agent-ID; System: NULL. Polymorph, ohne FK.
    actor_id             uuid,
    note                 text CHECK (char_length(note) BETWEEN 1 AND 2000),
    version_entity_type  text CHECK (version_entity_type IN (
                             'persona', 'playbook', 'resource',
                             'external_tool', 'system_prompt_template')),
    version_id           uuid,
    -- Massnahme (3.6); die Tabelle entsteht erst in Phase E, daher ohne FK.
    measure_id           uuid,
    element_target       text CHECK (element_target IN (
                             'persona', 'playbook', 'resource', 'external_tool',
                             'system_prompt_template', 'tool_policy', 'memory',
                             'model_limit')),
    element_entity_id    uuid,
    created_at           timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT agent_case_event_version_pair_check
        CHECK ((version_entity_type IS NULL) = (version_id IS NULL)),
    CONSTRAINT agent_case_event_addressed_version_check
        CHECK (event <> 'addressed' OR version_id IS NOT NULL),
    CONSTRAINT agent_case_event_measure_check
        CHECK (event NOT IN ('in_progress', 'verified') OR measure_id IS NOT NULL),
    CONSTRAINT agent_case_event_reason_check
        CHECK (event NOT IN ('reopened', 'dismissed') OR note IS NOT NULL),
    CONSTRAINT agent_case_event_agent_not_judge_check
        CHECK (actor_kind <> 'agent' OR event NOT IN ('addressed', 'verified', 'dismissed')),
    CONSTRAINT agent_case_event_human_actor_check
        CHECK (actor_kind <> 'human' OR actor_id IS NOT NULL),
    CONSTRAINT agent_case_event_element_check
        CHECK ((event IN ('element_assigned', 'element_unassigned'))
               = (element_target IS NOT NULL)),
    CONSTRAINT agent_case_event_element_entity_check
        CHECK (element_entity_id IS NULL
               OR element_target NOT IN ('tool_policy', 'model_limit')),
    CONSTRAINT agent_case_event_case_fkey
        FOREIGN KEY (workspace_id, case_id)
        REFERENCES agent_case (workspace_id, id) ON DELETE CASCADE
);

-- Juengstes Event je Fall (Status) und Verlauf.
CREATE INDEX IF NOT EXISTS agent_case_event_case_idx
    ON agent_case_event (workspace_id, case_id, created_at DESC, id DESC);

-- --- Zuordnung ---------------------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_case_element (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id      uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    case_id           uuid NOT NULL,
    target            text NOT NULL CHECK (target IN (
                          'persona', 'playbook', 'resource', 'external_tool',
                          'system_prompt_template', 'tool_policy', 'memory',
                          'model_limit')),
    entity_id         uuid,
    assigned_by_kind  text NOT NULL CHECK (assigned_by_kind IN ('human', 'agent')),
    assigned_by       uuid NOT NULL,
    -- clock_timestamp(): mehrere Zuordnungen eines PUT behalten ihre Reihenfolge.
    created_at        timestamptz NOT NULL DEFAULT clock_timestamp(),
    -- `entity_id` genau bei den beiden agentengebundenen Zielen NULL.
    CONSTRAINT agent_case_element_entity_check
        CHECK ((entity_id IS NULL) = (target IN ('tool_policy', 'model_limit'))),
    CONSTRAINT agent_case_element_case_fkey
        FOREIGN KEY (workspace_id, case_id)
        REFERENCES agent_case (workspace_id, id) ON DELETE CASCADE
);

-- Jedes Ziel hoechstens einmal je Fall; NULLS NOT DISTINCT, damit auch
-- `tool_policy`/`model_limit` (ohne entity_id) nur einmal vorkommen.
CREATE UNIQUE INDEX IF NOT EXISTS agent_case_element_unique_idx
    ON agent_case_element (workspace_id, case_id, target, entity_id) NULLS NOT DISTINCT;

-- Filter `target` der Liste und spaetere Musterzaehlung je Element (D5).
CREATE INDEX IF NOT EXISTS agent_case_element_target_idx
    ON agent_case_element (workspace_id, target, entity_id);

-- --- Schilderung (append-only) -----------------------------------------------

CREATE TABLE IF NOT EXISTS agent_case_statement (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id          uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    case_id               uuid NOT NULL,
    agent_id              uuid NOT NULL,
    followed_instruction  text NOT NULL CHECK (char_length(followed_instruction) <= 2000),
    missing_information   text NOT NULL CHECK (char_length(missing_information) <= 2000),
    conflict              text NOT NULL CHECK (char_length(conflict) <= 2000),
    created_at            timestamptz NOT NULL DEFAULT clock_timestamp(),
    -- Nur der betroffene Agent: (case_id, agent_id) muss der Fall selbst sein.
    CONSTRAINT agent_case_statement_case_agent_fkey
        FOREIGN KEY (workspace_id, case_id, agent_id)
        REFERENCES agent_case (workspace_id, id, agent_id) ON DELETE CASCADE
);

-- Neueste Schilderung je Fall.
CREATE INDEX IF NOT EXISTS agent_case_statement_case_idx
    ON agent_case_statement (workspace_id, case_id, created_at DESC);

-- --- agent_memory.converted_case_id (0091: „D1 ergaenzt den FK“) -------------

ALTER TABLE agent_memory DROP CONSTRAINT IF EXISTS agent_memory_converted_lesson_check;
ALTER TABLE agent_memory ADD CONSTRAINT agent_memory_converted_lesson_check
    CHECK (converted_case_id IS NULL OR kind = 'lesson');

ALTER TABLE agent_memory DROP CONSTRAINT IF EXISTS agent_memory_converted_case_fkey;
ALTER TABLE agent_memory ADD CONSTRAINT agent_memory_converted_case_fkey
    FOREIGN KEY (workspace_id, agent_id, converted_case_id)
    REFERENCES agent_case (workspace_id, agent_id, id);

CREATE INDEX IF NOT EXISTS agent_memory_converted_case_idx
    ON agent_memory (converted_case_id) WHERE converted_case_id IS NOT NULL;

-- --- RLS ---------------------------------------------------------------------

-- Strikt auf app.current_tenant (Workspace-Isolation, Muster 0066/0089).
DO $$
DECLARE
    tbl text;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'agent_case', 'agent_case_event', 'agent_case_element', 'agent_case_statement'
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
        -- Inhalt unveraenderlich: kein UPDATE. DELETE fuer Q6 (Hard-Delete).
        GRANT SELECT, INSERT, DELETE ON agent_case TO who2be_app;
        -- Append-only.
        GRANT SELECT, INSERT ON agent_case_event TO who2be_app;
        GRANT SELECT, INSERT ON agent_case_statement TO who2be_app;
        -- Zuordnung korrigierbar (3.3), aber nicht aenderbar: Austausch ist
        -- DELETE + INSERT mit Events.
        GRANT SELECT, INSERT, DELETE ON agent_case_element TO who2be_app;
    END IF;
END
$$;
