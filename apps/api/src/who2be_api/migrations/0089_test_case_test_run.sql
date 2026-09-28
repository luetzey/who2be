-- Migration 0089 — Pruefall + Prueflauf: `test_case`, `test_run`
-- (ADR-0053 Abschnitt 3.2 / 3.2.1, Lernschleife Phase B, Paket B1)
--
-- `test_case` haelt fest, WAS geprueft wird: eine Eingabe an einen Agenten
-- und die vom Menschen formulierte Erwartung. `test_run` haelt ein Ergebnis
-- fuer eine konkrete Elementversion fest.
--
-- Zugriffswege (Weiche P4, Option (a)): Die Pruefall-Menge einer
-- Elementversion ist die Vereinigung aus direkt gebundenen Pruefaellen
-- (`entity_type`, `entity_id`) und den Pruefaellen aller Agenten, die das
-- Element heute erreichen (`agent_id`). Deshalb ist `agent_id` Pflicht,
-- das Element optional, und beide Wege haben einen eigenen Index.
--
-- Unveraenderlichkeit (Muster 0044/0079 — Grants statt Trigger):
-- - `test_case`: der Inhalt ist fest, die Laufzeitrolle `who2be_app` darf
--   NUR die Spalte `status` aendern (spaltengenauer UPDATE-Grant). Eine
--   Korrektur ist ein neuer Pruefall mit `supersedes_id` plus `retired` am
--   alten. Kein DELETE-Grant: ein Pruefall wird zurueckgezogen, nicht
--   geloescht; er verschwindet nur mit seinem Agenten bzw. Workspace
--   (FK-CASCADE laeuft mit Owner-Rechten).
-- - `test_run`: append-only, NUR SELECT + INSERT.
-- Der Owner (Migrations-/Purge-Job) behaelt Vollzugriff (DSGVO-Erasure).
--
-- Konsistenz als DB-CHECK (die 422-Antwort `test_run_verdict_inconsistent`
-- baut der Service in B2 davor): `runs_total >= 1`,
-- `0 <= runs_passed <= runs_total`, `verdict = 'pass'` nur bei
-- `runs_passed = runs_total`. `attestation = 'human_rating'` verlangt
-- `reported_by_user_id`.
--
-- Workspace-Gleichheit per Composite-FK (Muster 0014/0023): Agent,
-- Vorgaenger-Pruefall und Pruefall eines Laufs stammen zwingend aus
-- demselben Workspace. Dafuer bekommt `agent` den bisher fehlenden
-- `UNIQUE (workspace_id, id)` als FK-Ziel. `ON DELETE SET NULL
-- (supersedes_id)` (Spaltenliste, ab Postgres 15) nullt nur den Verweis,
-- nicht die NOT-NULL-`workspace_id`.
--
-- Bewusst ohne FK: `entity_id` und `subject_version_id` (polymorph ueber
-- fuenf Tabellen, die Zugehoerigkeit prueft der Service) sowie
-- `origin_case_id`/`origin_measure_id` (Tabellen entstehen erst in D1).
--
-- Idempotenz: CREATE via IF NOT EXISTS; Constraint auf `agent` via
-- pg_constraint-Guard; Policy via DROP IF EXISTS + CREATE; GRANT
-- idempotent; pg_roles-Guard schuetzt On-Prem/Dev ohne who2be_app.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = (current_schema() || '.agent')::regclass
          AND conname = 'agent_workspace_id_id_key'
    ) THEN
        ALTER TABLE agent ADD CONSTRAINT agent_workspace_id_id_key UNIQUE (workspace_id, id);
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS test_case (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id       uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    -- Der Agent, dessen Verhalten geprueft wird (Pflicht, Weiche P4).
    agent_id           uuid NOT NULL,
    -- Optional: das Element, auf das der Pruefall zielt.
    entity_type        text CHECK (entity_type IN (
                           'persona', 'playbook', 'resource',
                           'external_tool', 'system_prompt_template')),
    entity_id          uuid,
    title              text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
    input              text NOT NULL CHECK (char_length(input) BETWEEN 1 AND 8000),
    expected_behavior  text NOT NULL
                       CHECK (char_length(expected_behavior) BETWEEN 1 AND 2000),
    check_kind         text NOT NULL
                       CHECK (check_kind IN ('human_rule', 'must_contain', 'must_not_contain')),
    check_pattern      text,
    origin_case_id     uuid,
    origin_measure_id  uuid,
    status             text NOT NULL DEFAULT 'active'
                       CHECK (status IN ('active', 'retired')),
    supersedes_id      uuid,
    created_by_kind    text NOT NULL CHECK (created_by_kind IN ('human', 'agent')),
    created_by         uuid NOT NULL,
    created_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, id),
    -- Element nur vollstaendig oder gar nicht.
    CONSTRAINT test_case_entity_pair_check
        CHECK ((entity_type IS NULL) = (entity_id IS NULL)),
    -- Muster nur (und dann Pflicht) bei den deterministischen Arten.
    CONSTRAINT test_case_check_pattern_check
        CHECK ((check_kind = 'human_rule') = (check_pattern IS NULL)
               AND (check_pattern IS NULL OR char_length(check_pattern) >= 1)),
    CONSTRAINT test_case_supersedes_self_check
        CHECK (supersedes_id IS NULL OR supersedes_id <> id),
    CONSTRAINT test_case_agent_fkey
        FOREIGN KEY (workspace_id, agent_id)
        REFERENCES agent (workspace_id, id) ON DELETE CASCADE,
    CONSTRAINT test_case_supersedes_fkey
        FOREIGN KEY (workspace_id, supersedes_id)
        REFERENCES test_case (workspace_id, id) ON DELETE SET NULL (supersedes_id)
);

-- Zugriffsweg 2 (Pruefaelle der betroffenen Agenten).
CREATE INDEX IF NOT EXISTS test_case_agent_idx
    ON test_case (workspace_id, agent_id, status);

-- Zugriffsweg 1 (direkt gebundene Pruefaelle eines Elements).
CREATE INDEX IF NOT EXISTS test_case_entity_idx
    ON test_case (workspace_id, entity_type, entity_id, status)
    WHERE entity_id IS NOT NULL;

-- FK-Index fuer ON DELETE SET NULL und die Korrekturkette.
CREATE INDEX IF NOT EXISTS test_case_supersedes_idx
    ON test_case (supersedes_id)
    WHERE supersedes_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS test_run (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id          uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    test_case_id          uuid NOT NULL,
    -- Die gepruefte Version (Entwurf oder aktiv); polymorph, ohne FK.
    subject_entity_type   text NOT NULL CHECK (subject_entity_type IN (
                              'persona', 'playbook', 'resource',
                              'external_tool', 'system_prompt_template')),
    subject_version_id    uuid NOT NULL,
    runs_total            integer NOT NULL CHECK (runs_total >= 1),
    runs_passed           integer NOT NULL,
    verdict               text NOT NULL CHECK (verdict IN ('pass', 'fail', 'error')),
    output_excerpt        text CHECK (char_length(output_excerpt) <= 4000),
    attestation           text NOT NULL
                          CHECK (attestation IN ('client_self_report', 'human_rating')),
    model_provider        text,
    model_name            text,
    reported_by_agent_id  uuid,
    reported_by_user_id   uuid,
    created_at            timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT test_run_runs_passed_check
        CHECK (runs_passed BETWEEN 0 AND runs_total),
    -- n/n: 'pass' nur, wenn jeder Lauf bestanden hat.
    CONSTRAINT test_run_verdict_pass_check
        CHECK (verdict <> 'pass' OR runs_passed = runs_total),
    -- Menschliche Bewertung ohne Menschen gibt es nicht.
    CONSTRAINT test_run_human_rating_user_check
        CHECK (attestation <> 'human_rating' OR reported_by_user_id IS NOT NULL),
    CONSTRAINT test_run_test_case_fkey
        FOREIGN KEY (workspace_id, test_case_id)
        REFERENCES test_case (workspace_id, id) ON DELETE CASCADE,
    CONSTRAINT test_run_reported_by_agent_fkey
        FOREIGN KEY (workspace_id, reported_by_agent_id)
        REFERENCES agent (workspace_id, id) ON DELETE SET NULL (reported_by_agent_id)
);

-- Letztes Ergebnis je Pruefall fuer eine Version (Bericht 6.2, Aktivierung 6.3).
CREATE INDEX IF NOT EXISTS test_run_case_version_idx
    ON test_run (workspace_id, test_case_id, subject_version_id, created_at DESC);

-- Alle Ergebnisse zu einer Version.
CREATE INDEX IF NOT EXISTS test_run_subject_idx
    ON test_run (workspace_id, subject_entity_type, subject_version_id);

-- FK-Index fuer ON DELETE SET NULL beim Agent-Delete.
CREATE INDEX IF NOT EXISTS test_run_reported_by_agent_idx
    ON test_run (reported_by_agent_id)
    WHERE reported_by_agent_id IS NOT NULL;

-- RLS strikt auf app.current_tenant (Workspace-Isolation, Muster 0066/0079).
DO $$
DECLARE
    tbl text;
BEGIN
    FOREACH tbl IN ARRAY ARRAY['test_case', 'test_run'] LOOP
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

-- Grants: test_case nur `status` aenderbar, test_run append-only.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT SELECT, INSERT ON test_case TO who2be_app;
        GRANT UPDATE (status) ON test_case TO who2be_app;
        GRANT SELECT, INSERT ON test_run TO who2be_app;
    END IF;
END
$$;
