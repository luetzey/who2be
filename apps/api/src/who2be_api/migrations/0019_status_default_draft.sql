-- Migration 0019 — Status-Default 'draft' fuer neue Versions (Phase 3-0)
-- Master-Plan: .claude/plan/2026-05-29-1900_phase-3-ux-polish.md §Track 0,
-- Detail-Plan: .claude/plan/2026-05-29-1817_3-0-models-migrations.md.
--
-- Hintergrund: Migration 0011 (persona/playbook) und 0015 (resource) haben den
-- Default auf 'inactive' gesetzt, weil zu dem Zeitpunkt nur die Active-Pfade
-- live waren. Mit der Status-Action-Bar (Phase 2.1b) ist 'inactive' fuer eine
-- frisch angelegte Version semantisch falsch — die UI rendert dann keine
-- Action-Bar (siehe F-02, F-03, F-13 im Phase-3-Plan). Neue v1 startet darum
-- als 'draft'.
--
-- Backfill: aktualisiert ausschliesslich die current_version-Zeile pro
-- Entity, und nur wenn dort 'inactive' liegt UND weder ein Active- noch ein
-- Draft-Geschwister existiert. Damit greift der partial-unique-index
-- *_draft_uniq aus 0011/0015 sauber (max. ein Draft je Entity).
--
-- Idempotenz: `ALTER COLUMN ... SET DEFAULT` ist idempotent. Die Backfill-
-- UPDATEs sind idempotent, weil der zweite Lauf keine `status='inactive'`-
-- Current-Rows ohne Active-/Draft-Schwester mehr findet.

ALTER TABLE persona_version
    ALTER COLUMN status SET DEFAULT 'draft';

ALTER TABLE playbook_version
    ALTER COLUMN status SET DEFAULT 'draft';

ALTER TABLE resource_version
    ALTER COLUMN status SET DEFAULT 'draft';

UPDATE persona_version pv
   SET status = 'draft'
  FROM persona p
 WHERE pv.persona_id = p.id
   AND pv.version    = p.current_version
   AND pv.status     = 'inactive'
   AND NOT EXISTS (
       SELECT 1 FROM persona_version sib
        WHERE sib.persona_id = p.id
          AND sib.status IN ('active', 'draft')
   );

UPDATE playbook_version pv
   SET status = 'draft'
  FROM playbook p
 WHERE pv.playbook_id = p.id
   AND pv.version     = p.current_version
   AND pv.status      = 'inactive'
   AND NOT EXISTS (
       SELECT 1 FROM playbook_version sib
        WHERE sib.playbook_id = p.id
          AND sib.status IN ('active', 'draft')
   );

UPDATE resource_version rv
   SET status = 'draft'
  FROM resource r
 WHERE rv.resource_id = r.id
   AND rv.version     = r.current_version
   AND rv.status      = 'inactive'
   AND NOT EXISTS (
       SELECT 1 FROM resource_version sib
        WHERE sib.resource_id = r.id
          AND sib.status IN ('active', 'draft')
   );
