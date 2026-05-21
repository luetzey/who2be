-- Migration 0004 — persona_playbook (TASK-176)
-- m:n-Verknuepfung Persona <-> Playbook. Im MVP eine reine Aktuell-Stand-
-- Relation, nicht eigenstaendig versioniert (ADR-0004, Konsequenzen).
--
-- owner_id + die beiden Composite-FKs erzwingen DB-seitig, dass eine
-- Verknuepfung nur Persona und Playbook desselben Owners verbinden kann
-- (Defense-in-Depth gegen Cross-Owner-Leaks; die App filtert zusaetzlich).

CREATE TABLE persona_playbook (
    persona_id  uuid NOT NULL,
    playbook_id uuid NOT NULL,
    owner_id    uuid NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (persona_id, playbook_id),
    FOREIGN KEY (owner_id, persona_id)
        REFERENCES persona (owner_id, id) ON DELETE CASCADE,
    FOREIGN KEY (owner_id, playbook_id)
        REFERENCES playbook (owner_id, id) ON DELETE CASCADE
);

CREATE INDEX persona_playbook_playbook_id_idx ON persona_playbook (playbook_id);
