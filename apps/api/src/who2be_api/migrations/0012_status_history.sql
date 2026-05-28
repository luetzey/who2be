-- Migration 0012 — status_history (TASK-300)
-- Append-only Audit-Trail fuer Status-Wechsel pro Entity (Plan §2.1.A).
-- Status-Wechsel bumpt KEINE Version — die Geschichte des Status lebt hier,
-- die Geschichte des Inhalts in persona_version / playbook_version.
--
-- entity_type laesst schon 'resource' zu (Vorgriff Phase 2.2): die Spalte hier
-- nachtraeglich zu erweitern ist teurer als von Anfang an offen zu lassen.
-- Schreibender Code kommt in 2.1b-1 (Status-Endpoints).

CREATE TABLE status_history (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type  text NOT NULL CHECK (entity_type IN ('persona', 'playbook', 'resource')),
    entity_id    uuid NOT NULL,
    from_status  text,
    to_status    text NOT NULL,
    changed_by   uuid NOT NULL,
    changed_at   timestamptz NOT NULL DEFAULT now(),
    note         text
);

CREATE INDEX status_history_entity_idx
    ON status_history (entity_type, entity_id, changed_at DESC);
