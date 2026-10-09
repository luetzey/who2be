-- Migration 0104 — Telemetrie faellt mit dem Workspace (Datenschutz-Befund)
--
-- `usage_event` und `agent_feedback` (0053) tragen `workspace_id` ohne
-- Fremdschluessel. Weder die Workspace-Loeschung (`WorkspaceRepository.delete`)
-- noch die Organization-CASCADE im Purge (`purge_organization`) erreichten
-- sie: nach einer Loeschung blieben die Zeilen samt `actor_id` (Person) und
-- Feedback-Freitext `note` verwaist zurueck (Art. 17 DSGVO).
--
-- (1) Bestand bereinigen: Zeilen, deren Workspace nicht mehr existiert,
--     sind keinem Mandanten mehr zuzuordnen und unter RLS fuer niemanden
--     sichtbar. Sie werden geloescht — sonst liesse sich der FK nicht anlegen.
--     `feedback_resolution` (0054) faellt ueber seinen FK auf
--     `agent_feedback` ON DELETE CASCADE mit; `agent_case.source_feedback_id`
--     (0100) wird per ON DELETE SET NULL geloest.
-- (2) FK `workspace_id -> workspace(id) ON DELETE CASCADE` auf beiden
--     Tabellen (Muster `status_history`, 0092). Der bestehende Index
--     `*_entity_idx` beginnt mit `workspace_id` und traegt den Cascade-Lookup.
--
-- Die Append-only-Grants aus 0053 bleiben: who2be_app erhaelt kein DELETE
-- auf `usage_event`; die Cascade laeuft als referentielle Aktion, nicht als
-- Recht der Laufzeitrolle.
--
-- Rueckweg (als eigene Vorwaerts-Migration — Migrationen sind
-- unveraenderlich): die beiden Constraints droppen. Geloeschte Waisen kommen
-- nicht zurueck; sie waren ohnehin keinem Mandanten mehr zuzuordnen.
--
-- Idempotent (Runner-Vertrag) und schema-aware (unqualifizierte Namen,
-- current_schema()): DELETE ist nach dem ersten Lauf leer, FK via
-- pg_constraint-Guard.

-- (1) Bestand ---------------------------------------------------------------------
DELETE FROM usage_event u
 WHERE NOT EXISTS (SELECT 1 FROM workspace w WHERE w.id = u.workspace_id);

DELETE FROM agent_feedback f
 WHERE NOT EXISTS (SELECT 1 FROM workspace w WHERE w.id = f.workspace_id);

-- (2) Fremdschluessel -------------------------------------------------------------
DO $$
DECLARE
    tname text;
BEGIN
    FOREACH tname IN ARRAY ARRAY['usage_event', 'agent_feedback']
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = (current_schema() || '.' || tname)::regclass
              AND conname = tname || '_workspace_id_fkey'
        ) THEN
            EXECUTE format(
                'ALTER TABLE %I ADD CONSTRAINT %I '
                'FOREIGN KEY (workspace_id) REFERENCES workspace (id) ON DELETE CASCADE',
                tname, tname || '_workspace_id_fkey'
            );
        END IF;
    END LOOP;
END
$$;
