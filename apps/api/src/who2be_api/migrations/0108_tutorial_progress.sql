-- 0108 — Tutorial-Fortschritt am Konto (ADR-0060, Onboarding P1).
--
-- Tutorials sind Daten (Katalog `packages/models/src/who2be_models/tutorials/
-- <id>.json`); gespeichert wird nur, was der Nutzer selbst getan hat:
--   * `tutorial_state`    — je (Nutzer, Tutorial): Begruessung gesehen, letzter
--                           Neustart.
--   * `tutorial_progress` — je (Nutzer, Tutorial, Schritt): abgehakt oder
--                           uebersprungen. Automatische Schritte (erster
--                           MCP-Abruf, Agent angelegt) leitet der Server ab und
--                           speichert sie nicht.
--
-- Kontoweit, nicht workspace-gebunden: dieselbe Person sieht ihren Stand in
-- jedem Workspace. Deshalb keine Mandantenspalte und keine RLS-Policy (Muster
-- `account_deletion`, 0038); jede Query der App filtert auf `user_id` des
-- authentifizierten Menschen. Kein FK auf den GoTrue-User (kein Schema tut
-- das, vgl. 0083) — die Konto-Loeschung raeumt explizit in
-- `purge_account_data` (`repositories/account_repository.py`).
--
-- Die ID-Form steht als CHECK hier und als Pydantic-Pattern in
-- `who2be_models.tutorial.TUTORIAL_ID_PATTERN`; beide gleich halten.

CREATE TABLE IF NOT EXISTS tutorial_state (
    user_id         uuid NOT NULL,
    tutorial_id     text NOT NULL
                    CONSTRAINT tutorial_state_tutorial_id_check
                    CHECK (tutorial_id ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND length(tutorial_id) <= 64),
    welcome_seen_at timestamptz,
    restarted_at    timestamptz,
    updated_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, tutorial_id)
);

CREATE TABLE IF NOT EXISTS tutorial_progress (
    user_id     uuid NOT NULL,
    tutorial_id text NOT NULL
                CONSTRAINT tutorial_progress_tutorial_id_check
                CHECK (tutorial_id ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND length(tutorial_id) <= 64),
    step_id     text NOT NULL
                CONSTRAINT tutorial_progress_step_id_check
                CHECK (step_id ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND length(step_id) <= 64),
    state       text NOT NULL
                CONSTRAINT tutorial_progress_state_check
                CHECK (state IN ('done', 'skipped')),
    changed_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, tutorial_id, step_id)
);

-- DML fuer die App-Rolle (Cloud). DELETE ist noetig: „Schritt wieder oeffnen“
-- und „Tutorial neu starten“ loeschen Zeilen. pg_roles-Guard fuer
-- On-Prem/Dev ohne `who2be_app`.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON tutorial_state, tutorial_progress TO who2be_app;
    END IF;
END
$$;
