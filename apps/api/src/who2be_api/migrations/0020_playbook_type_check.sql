-- Migration 0020 — playbook.type CHECK auf curated 6er-Set (Phase 3-0)
-- Master-Plan: .claude/plan/2026-05-29-1900_phase-3-ux-polish.md §Track 0.
--
-- Hintergrund: `playbook.type` ist bisher freier Text. Phase 3 ersetzt das
-- Frontend-Input durch ein Select mit kuratierten Werten
-- {prompt, instructions, snippet, workflow, checklist, faq}; damit das
-- Datenmodell die Auswahl mitziehen kann, ergaenzen wir hier den CHECK-
-- Constraint.
--
-- Backfill: bestehende Werte ausserhalb des Sets werden auf 'prompt'
-- gemapped (Default fuer „nicht klassifiziert"). Das ist die
-- konservativste Wahl — die UI zeigt 'prompt' als „generischer Prompt"-
-- Eintrag und der User kann nachpflegen.
--
-- Idempotenz: Die UPDATE ist idempotent (zweiter Lauf findet keine
-- unbekannten Werte mehr). Der CHECK-Constraint wird per `pg_constraint`-
-- Probe nur angelegt, wenn er noch nicht existiert — Statement-Replay ist
-- somit ein No-op.

UPDATE playbook
   SET type = 'prompt'
 WHERE type NOT IN ('prompt', 'instructions', 'snippet', 'workflow', 'checklist', 'faq');

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'playbook_type_check'
           AND conrelid = 'playbook'::regclass
    ) THEN
        ALTER TABLE playbook
            ADD CONSTRAINT playbook_type_check
            CHECK (type IN ('prompt', 'instructions', 'snippet', 'workflow', 'checklist', 'faq'));
    END IF;
END $$;
