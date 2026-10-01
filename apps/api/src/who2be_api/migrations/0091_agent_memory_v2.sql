-- Migration 0091 — Gedaechtnis 2.0: `agent_memory` erweitert, Historie
-- `agent_memory_event` (ADR-0053 Abschnitte 3.1, 3.1.1, 3.1.2, 5.1;
-- Lernschleife Phase C, Paket C1a)
--
-- Der Eintrag bleibt in `agent_memory` (Weiche M1): Waechter, Dublettenpruefung,
-- Vektor, Export und Triage behalten eine Quelle. Neu sind Art (`kind`),
-- Geltungsbereich (`scope`), Herkunft (`origin`), menschliche Bestaetigung,
-- Verfall, Wiederholungszaehler fuer Lernvorschlaege und der Verweis auf den
-- Fall, zu dem ein Lernvorschlag wurde.
--
-- Invarianten als DB-CHECK (3.1), damit kein kuenftiger Abrufpfad sie per
-- vergessenem Filter aushebeln kann:
-- - `kind='lesson'` => Status nie `active` (Lernvorschlaege fliessen nie in
--   einen Prompt; alle Abrufpfade filtern auf `status='active'`).
-- - `scope='user'` => `subject_user_id` gesetzt, `kind='user_fact'`,
--   `agent_id IS NULL` (Nutzergedaechtnis je Workspace UND Nutzer, Weiche
--   M2). Damit erreicht der Cascade auf `agent_id` nie einen Nutzerfakt.
-- - `scope='agent'` => `agent_id` gesetzt.
-- - `status='converted'` <=> `converted_case_id` gesetzt.
--
-- `agent_id` wird nullable (nur fuer `scope='user'`). Wer einen Eintrag
-- eingereicht hat, steht in `created_by_agent_id` (ON DELETE SET NULL): ein
-- Nutzerfakt ueberlebt den Agenten, der ihn zuerst gehoert hat.
--
-- `converted_case_id` bekommt BEWUSST KEINEN FK: die Fall-Tabelle legt erst
-- Paket D1 an; D1 ergaenzt den FK.
-- `subject_user_id` und `confirmed_by` ohne FK: Nutzer leben in der Auth-
-- Schicht (Muster `test_run.reported_by_user_id`, 0089).
--
-- Bestand (5.1, Weichen M6/M8): `kind='user_fact'`, `scope='agent'`,
-- `origin='legacy_unknown'`, `source='agent'`, `confirmed_at = updated_at`
-- fuer `status='active'` (unter `suggest` von einem Menschen freigegeben oder
-- unter `auto` uebernommen — nicht unterscheidbar, M6). `created_by_agent_id
-- = agent_id`: der einzige Schreibpfad bis hierher ist `save_memory` des
-- Agenten `agent_id` (`MemoryService.save` -> `PgMemoryRepository.insert`).
-- `origin` behaelt den Default `legacy_unknown`, bis C2a das Pflichtfeld im
-- Speicherpfad einfuehrt — ein neuer Eintrag ohne deklarierte Herkunft IST
-- bis dahin herkunfts-unbekannt.
--
-- Historie `agent_memory_event` (3.1.2): append-only, fuer `who2be_app` nur
-- SELECT + INSERT (Muster 0053/0089). Sie haengt per Composite-FK mit ON
-- DELETE CASCADE am Eintrag: Loeschen bleibt Hard-Delete (ADR-0044, DSGVO
-- Art. 17), die Historie geht mit; zurueck bleibt nur eine inhaltsfreie
-- `audit_log`-Zeile `memory.deleted`, die das Repository beim Loeschen
-- schreibt (Weiche M5). FK-Aktionen laufen mit Owner-Rechten, die enge
-- Grant-Lage der App-Rolle steht ihnen nicht im Weg.
--
-- Rueckweg (5.1, als eigene Vorwaerts-Migration — Migrationen sind
-- unveraenderlich): `scope='user'`-Zeilen exportieren und loeschen;
-- `expired`/`converted` -> `rejected`; `agent_memory_event` droppen; neue
-- CHECKs und Spalten droppen; Status-CHECK auf (pending, active, rejected);
-- `agent_id` wieder NOT NULL.
--
-- Idempotenz: ADD COLUMN IF NOT EXISTS; Constraints via DROP IF EXISTS + ADD
-- bzw. pg_constraint-Guard; CREATE TABLE/INDEX IF NOT EXISTS; Policy via
-- DROP IF EXISTS + CREATE; GRANT idempotent; pg_roles-Guard fuer On-Prem/Dev.

-- --- agent_memory: neue Spalten ---------------------------------------------

ALTER TABLE agent_memory
    ADD COLUMN IF NOT EXISTS kind                text NOT NULL DEFAULT 'user_fact',
    ADD COLUMN IF NOT EXISTS scope               text NOT NULL DEFAULT 'agent',
    ADD COLUMN IF NOT EXISTS subject_user_id     uuid,
    ADD COLUMN IF NOT EXISTS origin              text NOT NULL DEFAULT 'legacy_unknown',
    ADD COLUMN IF NOT EXISTS created_by_agent_id uuid,
    ADD COLUMN IF NOT EXISTS confirmed_at        timestamptz,
    ADD COLUMN IF NOT EXISTS confirmed_by        uuid,
    ADD COLUMN IF NOT EXISTS expires_at          timestamptz,
    ADD COLUMN IF NOT EXISTS occurrence_count    integer NOT NULL DEFAULT 1,
    -- Ohne FK bis D1 (Fall-Tabelle), siehe Kopfkommentar.
    ADD COLUMN IF NOT EXISTS converted_case_id   uuid;

ALTER TABLE agent_memory ALTER COLUMN agent_id DROP NOT NULL;

-- --- Bestand (5.1) -----------------------------------------------------------

UPDATE agent_memory SET source = 'agent' WHERE source IS DISTINCT FROM 'agent';
UPDATE agent_memory SET confirmed_at = updated_at
    WHERE status = 'active' AND confirmed_at IS NULL;
UPDATE agent_memory SET created_by_agent_id = agent_id
    WHERE created_by_agent_id IS NULL AND agent_id IS NOT NULL;

-- --- CHECKs ------------------------------------------------------------------

ALTER TABLE agent_memory DROP CONSTRAINT IF EXISTS agent_memory_status_check;
ALTER TABLE agent_memory ADD CONSTRAINT agent_memory_status_check
    CHECK (status IN ('pending', 'active', 'rejected', 'expired', 'converted'));

ALTER TABLE agent_memory DROP CONSTRAINT IF EXISTS agent_memory_kind_check;
ALTER TABLE agent_memory ADD CONSTRAINT agent_memory_kind_check
    CHECK (kind IN ('user_fact', 'agent_note', 'lesson'));

ALTER TABLE agent_memory DROP CONSTRAINT IF EXISTS agent_memory_scope_check;
ALTER TABLE agent_memory ADD CONSTRAINT agent_memory_scope_check
    CHECK (scope IN ('agent', 'user'));

ALTER TABLE agent_memory DROP CONSTRAINT IF EXISTS agent_memory_origin_check;
ALTER TABLE agent_memory ADD CONSTRAINT agent_memory_origin_check
    CHECK (origin IN ('user_stated', 'inferred', 'external_content', 'legacy_unknown'));

-- `source` setzt der Server aus dem Aufrufweg (M8); bisher ohne CHECK.
ALTER TABLE agent_memory DROP CONSTRAINT IF EXISTS agent_memory_source_check;
ALTER TABLE agent_memory ADD CONSTRAINT agent_memory_source_check
    CHECK (source IN ('agent', 'human', 'import'));

ALTER TABLE agent_memory DROP CONSTRAINT IF EXISTS agent_memory_occurrence_count_check;
ALTER TABLE agent_memory ADD CONSTRAINT agent_memory_occurrence_count_check
    CHECK (occurrence_count >= 1);

-- Ein Lernvorschlag kann in der Datenbank nie `active` werden.
ALTER TABLE agent_memory DROP CONSTRAINT IF EXISTS agent_memory_lesson_status_check;
ALTER TABLE agent_memory ADD CONSTRAINT agent_memory_lesson_status_check
    CHECK (kind <> 'lesson' OR status IN ('pending', 'rejected', 'converted'));

ALTER TABLE agent_memory DROP CONSTRAINT IF EXISTS agent_memory_user_scope_check;
ALTER TABLE agent_memory ADD CONSTRAINT agent_memory_user_scope_check
    CHECK (scope <> 'user'
           OR (subject_user_id IS NOT NULL AND kind = 'user_fact' AND agent_id IS NULL));

ALTER TABLE agent_memory DROP CONSTRAINT IF EXISTS agent_memory_agent_scope_check;
ALTER TABLE agent_memory ADD CONSTRAINT agent_memory_agent_scope_check
    CHECK (scope <> 'agent' OR agent_id IS NOT NULL);

ALTER TABLE agent_memory DROP CONSTRAINT IF EXISTS agent_memory_converted_check;
ALTER TABLE agent_memory ADD CONSTRAINT agent_memory_converted_check
    CHECK ((status = 'converted') = (converted_case_id IS NOT NULL));

-- --- Loeschkette Workspace ---------------------------------------------------

-- `workspace_id` hatte seit 0066 keinen FK: geloescht wurde bisher nur ueber
-- `agent_id` (CASCADE), und `agent` haengt am Workspace. Nutzerfakten
-- (`scope='user'`) haben kein `agent_id` mehr — ohne diesen FK ueberlebten sie
-- das Loeschen von Workspace und Organisation (Purge, ADR-0044, DSGVO Art. 17,
-- Weiche M5). Der Bestand ist waisenfrei: jede Zeile hing bisher ueber
-- `agent_id` an einem Agenten desselben Workspace (das belegt auch der
-- Composite-FK `agent_memory_created_by_agent_fkey` unten, der denselben
-- Bestand prueft). Index: `agent_memory_scope_idx` fuehrt mit `workspace_id`.
--
-- Bewusst ohne `memory.deleted`-Audit: Faellt ein Eintrag per Cascade (Agent,
-- Workspace, Organisation), dokumentiert die Loeschung des Elternobjekts den
-- Vorgang; die inhaltsfreie Audit-Zeile je Eintrag schreibt nur das gezielte
-- Loeschen im Repository.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = (current_schema() || '.agent_memory')::regclass
          AND conname = 'agent_memory_workspace_fkey'
    ) THEN
        ALTER TABLE agent_memory
            ADD CONSTRAINT agent_memory_workspace_fkey
            FOREIGN KEY (workspace_id) REFERENCES workspace (id) ON DELETE CASCADE;
    END IF;
END
$$;

-- --- FK-Ziele und Einreicher -------------------------------------------------

-- Composite-Ziel fuer die Historie (Workspace-Gleichheit, Muster 0089).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = (current_schema() || '.agent_memory')::regclass
          AND conname = 'agent_memory_workspace_id_id_key'
    ) THEN
        ALTER TABLE agent_memory
            ADD CONSTRAINT agent_memory_workspace_id_id_key UNIQUE (workspace_id, id);
    END IF;
END
$$;

-- Einreicher im selben Workspace; beim Agent-Delete nur den Verweis nullen
-- (Spaltenliste, ab Postgres 15). `agent (workspace_id, id)` ist seit 0089
-- eindeutig.
ALTER TABLE agent_memory DROP CONSTRAINT IF EXISTS agent_memory_created_by_agent_fkey;
ALTER TABLE agent_memory ADD CONSTRAINT agent_memory_created_by_agent_fkey
    FOREIGN KEY (workspace_id, created_by_agent_id)
    REFERENCES agent (workspace_id, id) ON DELETE SET NULL (created_by_agent_id);

CREATE INDEX IF NOT EXISTS agent_memory_created_by_agent_idx
    ON agent_memory (created_by_agent_id)
    WHERE created_by_agent_id IS NOT NULL;

-- Zaehlabfrage und Abruf des Nutzergedaechtnisses je (workspace_id,
-- subject_user_id) (3.1.1, `MEMORY_MAX_PER_USER`).
CREATE INDEX IF NOT EXISTS agent_memory_user_scope_idx
    ON agent_memory (workspace_id, subject_user_id, status, created_at DESC)
    WHERE scope = 'user';

-- --- Historie (3.1.2) --------------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_memory_event (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    memory_id    uuid NOT NULL,
    event        text NOT NULL CHECK (event IN (
                     'created', 'auto_activated', 'approved', 'rejected', 'edited',
                     'confirmed', 'expired', 'reactivated', 'change_proposed',
                     'delete_proposed', 'proposal_accepted', 'proposal_rejected',
                     'rolled_back', 'converted', 'merged')),
    actor_kind   text NOT NULL CHECK (actor_kind IN ('human', 'agent', 'system')),
    -- Mensch: Nutzer-ID; Agent/System: NULL (der Agent steht in agent_id).
    actor_id     uuid,
    agent_id     uuid,
    -- Schnappschuss von fact, category, importance, status, kind, origin.
    before       jsonb,
    after        jsonb,
    reason       text CHECK (char_length(reason) <= 500),
    created_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT agent_memory_event_memory_fkey
        FOREIGN KEY (workspace_id, memory_id)
        REFERENCES agent_memory (workspace_id, id) ON DELETE CASCADE,
    CONSTRAINT agent_memory_event_agent_fkey
        FOREIGN KEY (workspace_id, agent_id)
        REFERENCES agent (workspace_id, id) ON DELETE SET NULL (agent_id)
);

CREATE INDEX IF NOT EXISTS agent_memory_event_memory_idx
    ON agent_memory_event (workspace_id, memory_id, created_at);

-- FK-Index fuer ON DELETE SET NULL beim Agent-Delete.
CREATE INDEX IF NOT EXISTS agent_memory_event_agent_idx
    ON agent_memory_event (agent_id)
    WHERE agent_id IS NOT NULL;

-- RLS strikt auf app.current_tenant (Muster 0066/0089).
DO $$
BEGIN
    EXECUTE 'ALTER TABLE agent_memory_event ENABLE ROW LEVEL SECURITY';
    EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON agent_memory_event';
    EXECUTE format(
        'CREATE POLICY tenant_isolation ON agent_memory_event '
        'USING (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid) '
        'WITH CHECK (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid)',
        'app.current_tenant', '', 'app.current_tenant', ''
    );
END
$$;

-- Append-only: NUR SELECT + INSERT.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT SELECT, INSERT ON agent_memory_event TO who2be_app;
    END IF;
END
$$;
