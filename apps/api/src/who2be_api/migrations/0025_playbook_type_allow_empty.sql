-- Migration 0025 — playbook.type CHECK um Leerstring erweitern (Welle 4)
--
-- Hintergrund: Welle 4 erlaubt das Anlegen von Playbooks mit nur `name`
-- als Pflichtfeld. `type` bleibt leer bis zum Promote-Step. Der bisherige
-- CHECK-Constraint (Migration 0020) laesst den Leerstring nicht zu.
--
-- Aenderung: CHECK-Constraint `playbook_type_check` wird um '' ergaenzt.
-- Der denormalisierte `type`-Wert ist in der Liste fuer Drafts dann '',
-- was im UI korrekt als "kein Typ gesetzt" interpretiert wird.
-- Promote-Validation prueft `content->>'type'` und blockiert bei Leerstring.
--
-- Idempotenz: DROP/ADD ueber pg_constraint-Probe — Replay ist No-op.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'playbook_type_check'
           AND conrelid = 'playbook'::regclass
    ) THEN
        ALTER TABLE playbook DROP CONSTRAINT playbook_type_check;
    END IF;

    ALTER TABLE playbook
        ADD CONSTRAINT playbook_type_check
        CHECK (type IN ('', 'prompt', 'instructions', 'snippet', 'workflow', 'checklist', 'faq'));
END $$;
