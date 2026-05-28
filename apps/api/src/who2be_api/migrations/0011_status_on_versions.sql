-- Migration 0011 — status pro Version (TASK-300)
-- Status-Workflow draft/review/active/inactive lebt pro Version (Plan §2.1.A
-- + 2.1b). DB-erzwungene Invariante "max. 1 Draft / 1 Review / 1 Active je
-- Entity" via partial unique indices.
--
-- Backfill in derselben Migration: die aktuell zeigenden current_version-
-- Eintraege werden auf 'active' gehoben, alle anderen bleiben auf dem Default
-- 'inactive'. Damit ist die Invariante nach Migration ohne weitere Schritte
-- erfuellt.

ALTER TABLE persona_version
    ADD COLUMN status text NOT NULL DEFAULT 'inactive'
        CHECK (status IN ('draft', 'review', 'active', 'inactive'));

ALTER TABLE playbook_version
    ADD COLUMN status text NOT NULL DEFAULT 'inactive'
        CHECK (status IN ('draft', 'review', 'active', 'inactive'));

UPDATE persona_version pv
    SET status = 'active'
    FROM persona p
    WHERE pv.persona_id = p.id
      AND pv.version = p.current_version;

UPDATE playbook_version pv
    SET status = 'active'
    FROM playbook p
    WHERE pv.playbook_id = p.id
      AND pv.version = p.current_version;

CREATE UNIQUE INDEX persona_version_active_uniq
    ON persona_version (persona_id) WHERE status = 'active';
CREATE UNIQUE INDEX persona_version_draft_uniq
    ON persona_version (persona_id) WHERE status = 'draft';
CREATE UNIQUE INDEX persona_version_review_uniq
    ON persona_version (persona_id) WHERE status = 'review';

CREATE UNIQUE INDEX playbook_version_active_uniq
    ON playbook_version (playbook_id) WHERE status = 'active';
CREATE UNIQUE INDEX playbook_version_draft_uniq
    ON playbook_version (playbook_id) WHERE status = 'draft';
CREATE UNIQUE INDEX playbook_version_review_uniq
    ON playbook_version (playbook_id) WHERE status = 'review';
