-- Migration 0014 — workspace_id final-lock + Composite-FK-Switch (TASK-301)
-- Zweite Stufe des Tenant-Schwenks: nach dem Backfill in 0013 sind alle
-- workspace_id-Spalten gefuellt, jetzt:
--   - SET NOT NULL auf persona/playbook/api_token.workspace_id
--   - UNIQUE (workspace_id, id) je Tabelle als Ziel der neuen Composite-FKs
--   - persona_playbook bekommt workspace_id-Spalte + Backfill aus persona
--   - alte Composite-FKs (owner_id, persona_id|playbook_id) weg, neue auf
--     (workspace_id, persona_id|playbook_id) — Defense-in-Depth analog 0004,
--     jetzt entlang des neuen Mandanten-Schluessels.
-- owner_id bleibt als Audit-Spalte erhalten (created_by-Bruecke).
--
-- Idempotenz: SET NOT NULL ist DDL-idempotent (kein Fehler bei bereits
-- gesetztem NOT NULL); UNIQUE/COLUMN/CONSTRAINT-Operationen sind in
-- DO-Bloecke gepackt, die ueber information_schema/pg_constraint pruefen,
-- ob sie schon ausgefuehrt wurden. Damit kann das Statement auch manuell
-- (z.B. im Phase-21-Idempotenztest) wiederholt werden.

ALTER TABLE persona ALTER COLUMN workspace_id SET NOT NULL;
ALTER TABLE playbook ALTER COLUMN workspace_id SET NOT NULL;
ALTER TABLE api_token ALTER COLUMN workspace_id SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = (current_schema() || '.persona')::regclass
          AND conname = 'persona_workspace_id_id_key'
    ) THEN
        ALTER TABLE persona ADD CONSTRAINT persona_workspace_id_id_key UNIQUE (workspace_id, id);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = (current_schema() || '.playbook')::regclass
          AND conname = 'playbook_workspace_id_id_key'
    ) THEN
        ALTER TABLE playbook ADD CONSTRAINT playbook_workspace_id_id_key UNIQUE (workspace_id, id);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = (current_schema() || '.api_token')::regclass
          AND conname = 'api_token_workspace_id_id_key'
    ) THEN
        ALTER TABLE api_token ADD CONSTRAINT api_token_workspace_id_id_key UNIQUE (workspace_id, id);
    END IF;
END
$$;

ALTER TABLE persona_playbook
    ADD COLUMN IF NOT EXISTS workspace_id uuid;

UPDATE persona_playbook pp
SET workspace_id = p.workspace_id
FROM persona p
WHERE pp.persona_id = p.id
  AND pp.workspace_id IS NULL;

ALTER TABLE persona_playbook ALTER COLUMN workspace_id SET NOT NULL;

-- Alte Composite-FKs (auf owner_id) entfernen. Constraint-Namen aus 0004
-- sind Auto-generiert (mehrspaltig + dieselbe Spalte owner_id zweimal); ueber
-- pg_constraint per confrelid suchen, statt fragile Namen anzunehmen.
DO $$
DECLARE
    cname text;
BEGIN
    FOR cname IN
        SELECT conname FROM pg_constraint
        WHERE conrelid = (current_schema() || '.persona_playbook')::regclass
          AND contype = 'f'
          AND confrelid = (current_schema() || '.persona')::regclass
          AND (
            SELECT array_agg(attname ORDER BY attnum)
            FROM pg_attribute
            WHERE attrelid = (current_schema() || '.persona_playbook')::regclass
              AND attnum = ANY(conkey)
          ) @> ARRAY['owner_id'::name, 'persona_id'::name]
    LOOP
        EXECUTE format(
            'ALTER TABLE persona_playbook DROP CONSTRAINT %I',
            cname
        );
    END LOOP;

    FOR cname IN
        SELECT conname FROM pg_constraint
        WHERE conrelid = (current_schema() || '.persona_playbook')::regclass
          AND contype = 'f'
          AND confrelid = (current_schema() || '.playbook')::regclass
          AND (
            SELECT array_agg(attname ORDER BY attnum)
            FROM pg_attribute
            WHERE attrelid = (current_schema() || '.persona_playbook')::regclass
              AND attnum = ANY(conkey)
          ) @> ARRAY['owner_id'::name, 'playbook_id'::name]
    LOOP
        EXECUTE format(
            'ALTER TABLE persona_playbook DROP CONSTRAINT %I',
            cname
        );
    END LOOP;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = (current_schema() || '.persona_playbook')::regclass
          AND conname = 'persona_playbook_workspace_id_persona_id_fkey'
    ) THEN
        ALTER TABLE persona_playbook
            ADD CONSTRAINT persona_playbook_workspace_id_persona_id_fkey
            FOREIGN KEY (workspace_id, persona_id)
            REFERENCES persona (workspace_id, id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = (current_schema() || '.persona_playbook')::regclass
          AND conname = 'persona_playbook_workspace_id_playbook_id_fkey'
    ) THEN
        ALTER TABLE persona_playbook
            ADD CONSTRAINT persona_playbook_workspace_id_playbook_id_fkey
            FOREIGN KEY (workspace_id, playbook_id)
            REFERENCES playbook (workspace_id, id) ON DELETE CASCADE;
    END IF;
END
$$;
