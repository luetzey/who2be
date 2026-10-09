-- Migration 0102 — Laufprotokoll der Hintergrund-Routinen: `routine_run`,
-- `worker_heartbeat` (ADR-0057 §5/§6, Worker-Welle Paket P1a)
--
-- Der eingebaute Worker fuehrt Who2Be-eigene Wartungsroutinen aus (Purge,
-- Verfall, Aufraeumen des eigenen Protokolls). Beide Tabellen tragen KEINE
-- Mandantendaten: keine `workspace_id`, keine `org_id`, keine RLS. Sie liegen
-- im Owner-Schema; geschrieben wird nur ueber die Owner-Verbindung
-- (`DATABASE_URL`, Modul `worker/store.py`).
--
-- `routine_run` — eine Zeile je Lauf.
-- - UNIQUE (routine, slot) ist die Exklusivitaet (§5): genau wer die Zeile per
--   `INSERT … ON CONFLICT (routine, slot) DO NOTHING RETURNING id` zurueck-
--   bekommt, fuehrt den Slot aus. CLI- und manuelle Laeufe tragen ihre
--   Startzeit als `slot`.
-- - `status`: `running` bis zum Abschluss, dann `succeeded`, `failed` oder
--   `skipped` (Advisory-Lock belegt). `finished_at` ist genau bei `running`
--   NULL (CHECK).
-- - `result`: nur Zaehler. Der CHECK verlangt ein JSON-Objekt, dessen Werte
--   ausnahmslos Zahlen sind — Text mit Inhalten oder personenbezogenen Daten
--   passt nicht hinein.
-- - `error_class`: nur der Name der Exception-Klasse (Bezeichner-Muster, kein
--   Leerzeichen, also keine Fehlermeldung mit Daten), nur bei `failed`.
--   Abgebrochene Laeufe (Heartbeat aelter als die Schwelle) bekommen
--   `Abandoned`.
-- - `heartbeat_at`: der Ausfuehrende frischt ihn waehrend des Laufs auf.
--
-- `worker_heartbeat` — eine Zeile je Worker-Prozess (`worker_id` =
-- `hostname:pid`), je Tick per Upsert aufgefrischt. Grundlage fuer den
-- Container-Healthcheck und das Health-Feld `worker`. Zeilen frueherer
-- Prozesse bleiben stehen, bis eine Aufraeum-Routine sie entfernt.
--
-- Grants: `who2be_app` bekommt nur SELECT (Betreiber-Endpunkt, §7). Kein
-- INSERT, UPDATE oder DELETE fuer die Laufzeitrolle.
--
-- Org-Transfer: beide Tabellen sind instanzweit und stehen in
-- `apps/api/src/who2be_api/core/org_transfer.py#GLOBAL_TABLES` (nie Teil eines Org-Archivs).
--
-- Rueckweg (als eigene Vorwaerts-Migration): beide Tabellen droppen. Kein
-- anderes Objekt verweist auf sie.
--
-- Idempotenz: CREATE via IF NOT EXISTS; GRANT idempotent; pg_roles-Guard
-- schuetzt On-Prem/Dev ohne who2be_app.

-- --- Laufprotokoll -----------------------------------------------------------

CREATE TABLE IF NOT EXISTS routine_run (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Registry-Name; Kleinbuchstaben, Ziffern, Bindestrich (wird fuer
    -- `WHO2BE_ROUTINE_<NAME>_*` in Grossbuchstaben umgesetzt, §4).
    routine       text NOT NULL CHECK (routine ~ '^[a-z][a-z0-9-]{0,62}$'),
    slot          timestamptz NOT NULL,
    trigger       text NOT NULL CHECK (trigger IN ('schedule', 'cli', 'manual')),
    status        text NOT NULL DEFAULT 'running'
                  CHECK (status IN ('running', 'succeeded', 'failed', 'skipped')),
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    heartbeat_at  timestamptz NOT NULL DEFAULT now(),
    result        jsonb,
    error_class   text,
    worker_id     text NOT NULL CHECK (char_length(worker_id) BETWEEN 1 AND 255),
    CONSTRAINT routine_run_routine_slot_key UNIQUE (routine, slot),
    CONSTRAINT routine_run_finished_check
        CHECK ((status = 'running') = (finished_at IS NULL)),
    -- Nur ein Klassenname (kein Leerzeichen, keine Meldung), nur bei `failed`.
    CONSTRAINT routine_run_error_class_check
        CHECK (error_class IS NULL OR (
            status = 'failed'
            AND error_class ~ '^[A-Za-z_][A-Za-z0-9_.]{0,199}$'
        )),
    CONSTRAINT routine_run_result_counters_check
        CHECK (result IS NULL OR (
            jsonb_typeof(result) = 'object'
            AND NOT jsonb_path_exists(result, '$.* ? (@.type() != "number")')
        ))
);

-- Letzter Lauf je Routine (Betreiber-Sicht).
CREATE INDEX IF NOT EXISTS routine_run_routine_started_idx
    ON routine_run (routine, started_at DESC);
-- Letzter Erfolg je Routine (catch_up, Betreiber-Sicht).
CREATE INDEX IF NOT EXISTS routine_run_routine_success_idx
    ON routine_run (routine, finished_at DESC)
    WHERE status = 'succeeded';
-- Retention: Zeilen aelter als 90 Tage (Routine `routine-run-retention`).
CREATE INDEX IF NOT EXISTS routine_run_started_idx
    ON routine_run (started_at);
-- Abgebrochene Laeufe finden: offene Laeufe nach Heartbeat.
CREATE INDEX IF NOT EXISTS routine_run_running_heartbeat_idx
    ON routine_run (heartbeat_at)
    WHERE status = 'running';

-- --- Worker-Heartbeat --------------------------------------------------------

CREATE TABLE IF NOT EXISTS worker_heartbeat (
    worker_id  text PRIMARY KEY CHECK (char_length(worker_id) BETWEEN 1 AND 255),
    seen_at    timestamptz NOT NULL DEFAULT now(),
    version    text NOT NULL CHECK (char_length(version) BETWEEN 1 AND 100)
);

-- „Worker zuletzt gesehen“.
CREATE INDEX IF NOT EXISTS worker_heartbeat_seen_idx
    ON worker_heartbeat (seen_at DESC);

-- --- Grants ------------------------------------------------------------------

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        -- Nur lesen (Betreiber-Endpunkt). Geschrieben wird ueber den Owner.
        GRANT SELECT ON routine_run TO who2be_app;
        GRANT SELECT ON worker_heartbeat TO who2be_app;
    END IF;
END
$$;
