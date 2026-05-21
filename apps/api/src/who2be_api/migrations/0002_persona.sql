-- Migration 0002 — persona + persona_version (TASK-175)
-- Versionierung ueber separate History-Tabelle (ADR-0004): die Identitaets-
-- Zeile `persona` traegt den aktuellen Stand, jeder Update schreibt einen
-- unveraenderlichen jsonb-Snapshot in `persona_version`.

CREATE TABLE persona (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id        uuid NOT NULL,
    name            text NOT NULL,
    current_version int NOT NULL DEFAULT 1,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    -- Ziel fuer den Composite-FK aus persona_playbook: erzwingt DB-seitig,
    -- dass eine Verknuepfung nur Personae desselben Owners referenziert.
    UNIQUE (owner_id, id)
);

CREATE INDEX persona_owner_id_idx ON persona (owner_id);

CREATE TABLE persona_version (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    persona_id uuid NOT NULL REFERENCES persona (id) ON DELETE CASCADE,
    version    int NOT NULL,
    content    jsonb NOT NULL,
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (persona_id, version)
);
