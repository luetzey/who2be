-- Migration 0035 — workspace_id-Denormalisierung fuer RLS (Track I, Plan §3.1)
-- Plan: .claude/plan/2026-06-02-1819_followups-rls-mollie-auth-fsl.md (R1/R2)
--
-- RLS-Policies (0037) brauchen den Mandantenschluessel direkt auf jeder Zeile,
-- damit die USING-Klausel ohne Join auswertet. Die vier *_version-Tabellen
-- erben workspace_id von ihrer Identitaets-Zeile (persona/playbook/resource/
-- system_prompt_template); hier wird er denormalisiert, gebackfillt und hart
-- gelockt (NOT NULL).
--
-- Die vier Link-Tabellen aus dem Plan (persona_playbook 0014, playbook_resource
-- _link 0016, playbook_composition 0028, resource_composition 0032) tragen
-- workspace_id BEREITS NOT NULL — sie sind schon denormalisiert. Diese
-- Migration laesst sie unangetastet (kein redundantes ALTER).
--
-- Idempotenz (Runner-Vertrag, core/migrations.py): ADD COLUMN IF NOT EXISTS,
-- Backfill nur auf NULL-Zeilen, SET NOT NULL ist DDL-idempotent, Index/FK
-- ueber IF NOT EXISTS bzw. pg_constraint-Guard. Schema-aware (unqualifizierte
-- Namen + current_schema()), damit der Isolations-Test in eigenem Schema
-- repliziert.

-- Auto-Fill-Trigger: leitet workspace_id auf den *_version-Tabellen aus der
-- Identitaets-Zeile ab. So bleiben die Repo-INSERTs unveraendert (kein neuer
-- Spalten-Parameter, "Repos nur Connection-Plumbing"), die denormalisierte
-- Spalte ist immer mit dem Parent konsistent (kein Drift), und NEW.workspace_id
-- ist vor der NOT-NULL-/RLS-WITH-CHECK-Pruefung gesetzt. SECURITY INVOKER:
-- der Parent-Lookup laeuft unter RLS — ein Cross-Tenant-INSERT findet die
-- (unsichtbare) Parent-Zeile nicht und scheitert fail-closed.
CREATE OR REPLACE FUNCTION w2b_fill_version_workspace_id() RETURNS trigger
LANGUAGE plpgsql AS $fn$
DECLARE
    ws uuid;
BEGIN
    EXECUTE format('SELECT workspace_id FROM %I WHERE id = $1', TG_ARGV[0])
        INTO ws
        USING ((to_jsonb(NEW) ->> TG_ARGV[1])::uuid);
    NEW.workspace_id := ws;
    RETURN NEW;
END;
$fn$;

-- persona_version --------------------------------------------------------------
ALTER TABLE persona_version ADD COLUMN IF NOT EXISTS workspace_id uuid;
UPDATE persona_version pv
   SET workspace_id = p.workspace_id
  FROM persona p
 WHERE pv.persona_id = p.id
   AND pv.workspace_id IS NULL;
ALTER TABLE persona_version ALTER COLUMN workspace_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS persona_version_workspace_id_idx
    ON persona_version (workspace_id);

-- playbook_version -------------------------------------------------------------
ALTER TABLE playbook_version ADD COLUMN IF NOT EXISTS workspace_id uuid;
UPDATE playbook_version pv
   SET workspace_id = p.workspace_id
  FROM playbook p
 WHERE pv.playbook_id = p.id
   AND pv.workspace_id IS NULL;
ALTER TABLE playbook_version ALTER COLUMN workspace_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS playbook_version_workspace_id_idx
    ON playbook_version (workspace_id);

-- resource_version -------------------------------------------------------------
ALTER TABLE resource_version ADD COLUMN IF NOT EXISTS workspace_id uuid;
UPDATE resource_version rv
   SET workspace_id = r.workspace_id
  FROM resource r
 WHERE rv.resource_id = r.id
   AND rv.workspace_id IS NULL;
ALTER TABLE resource_version ALTER COLUMN workspace_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS resource_version_workspace_id_idx
    ON resource_version (workspace_id);

-- system_prompt_template_version ----------------------------------------------
ALTER TABLE system_prompt_template_version ADD COLUMN IF NOT EXISTS workspace_id uuid;
UPDATE system_prompt_template_version sv
   SET workspace_id = t.workspace_id
  FROM system_prompt_template t
 WHERE sv.template_id = t.id
   AND sv.workspace_id IS NULL;
ALTER TABLE system_prompt_template_version ALTER COLUMN workspace_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS system_prompt_template_version_workspace_id_idx
    ON system_prompt_template_version (workspace_id);

-- Referentielle Integritaet: workspace_id der *_version-Zeilen folgt der
-- Identitaets-Zeile (CASCADE), zusaetzlich an workspace gepinnt. Composite-FK
-- auf (workspace_id, <id>) erzwingt, dass die denormalisierte Spalte mit dem
-- Parent uebereinstimmt — kein Drift moeglich. pg_constraint-Guard fuer
-- Idempotenz/Replay.
DO $$
DECLARE
    t record;
BEGIN
    FOR t IN
        SELECT * FROM (VALUES
            ('persona_version', 'persona', 'persona_id'),
            ('playbook_version', 'playbook', 'playbook_id'),
            ('resource_version', 'resource', 'resource_id'),
            ('system_prompt_template_version', 'system_prompt_template', 'template_id')
        ) AS v(child, parent, fk_col)
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = (current_schema() || '.' || t.child)::regclass
              AND conname = t.child || '_ws_parent_fkey'
        ) THEN
            EXECUTE format(
                'ALTER TABLE %I ADD CONSTRAINT %I '
                'FOREIGN KEY (workspace_id, %I) REFERENCES %I (workspace_id, id) '
                'ON DELETE CASCADE',
                t.child, t.child || '_ws_parent_fkey', t.fk_col, t.parent
            );
        END IF;
    END LOOP;
END
$$;

-- Auto-Fill-Trigger je *_version-Tabelle (idempotent via DROP IF EXISTS).
DO $$
DECLARE
    t record;
BEGIN
    FOR t IN
        SELECT * FROM (VALUES
            ('persona_version', 'persona', 'persona_id'),
            ('playbook_version', 'playbook', 'playbook_id'),
            ('resource_version', 'resource', 'resource_id'),
            ('system_prompt_template_version', 'system_prompt_template', 'template_id')
        ) AS v(child, parent, fk_col)
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I', t.child || '_fill_ws', t.child);
        EXECUTE format(
            'CREATE TRIGGER %I BEFORE INSERT OR UPDATE ON %I '
            'FOR EACH ROW EXECUTE FUNCTION w2b_fill_version_workspace_id(%L, %L)',
            t.child || '_fill_ws', t.child, t.parent, t.fk_col
        );
    END LOOP;
END
$$;
