-- Migration 0105 — Knowledge Base und Passagen fallen mit dem Workspace
-- (Datenschutz-Befund aus #888)
--
-- `kb_node`, `kb_edge`, `kb_edge_evidence`, `kb_conflict` (0077) und
-- `content_chunk` (0070) tragen `workspace_id` ohne Fremdschluessel. Weder die
-- Workspace-Loeschung (`WorkspaceRepository.delete`) noch die
-- Organization-CASCADE im Purge (`purge_organization`) erreichten sie: nach
-- einer Loeschung blieben Aussagen (`kb_node.content`), Begruendungen
-- (`kb_conflict.reason`) und Inhaltspassagen (`content_chunk.text`) samt
-- `created_by` verwaist zurueck (Art. 17 DSGVO). Der Orphan-Sweep in
-- `core/chunk_backfill.py` laeuft nur bei CLI/Start-Sync und nur fuer
-- fehlende Entities — kein Loeschpfad. Kanten hingen allein ueber die
-- NULLABLE `from_node_id`/`to_node_id` an `kb_node`; eine unaufgeloeste Kante
-- fiel nicht einmal mit ihren Nodes.
--
-- FK statt explizitem DELETE im Purge: jeder Loeschweg des Workspace (API,
-- Org-Purge, Personal-Org im Account-Purge, kuenftige) greift automatisch —
-- dasselbe Muster wie 0092 (`status_history`) und 0104 (Telemetrie).
-- `kb_node_source_area` braucht keinen eigenen FK: sie haengt per CASCADE an
-- `kb_node` und `work_area`.
--
-- (1) Bestand bereinigen: Zeilen, deren Workspace nicht mehr existiert, sind
--     keinem Mandanten mehr zuzuordnen und unter RLS fuer niemanden sichtbar.
--     Sie werden geloescht — sonst liesse sich der FK nicht anlegen.
--     `kb_edge_evidence`/`kb_node_source_area` fallen ueber ihre FKs auf
--     `kb_edge`/`kb_node` mit; der eigene DELETE auf `kb_edge_evidence` faengt
--     Evidence ab, deren Workspace weg ist, deren Kante aber nicht.
-- (2) FK `workspace_id -> workspace(id) ON DELETE CASCADE` auf allen fuenf
--     Tabellen. Die Cascade-Lookups tragen die bestehenden `*_workspace_id_idx`
--     bzw. `content_chunk_entity_idx` (beginnt mit `workspace_id`); fuer
--     `kb_conflict` gibt es bisher nur einen Teilindex (offene Konflikte),
--     daher (3) ein voller Index.
--
-- Grants bleiben unveraendert (0070/0077). Die Cascade laeuft als
-- referentielle Aktion, nicht als Recht der Laufzeitrolle.
--
-- Rueckweg (als eigene Vorwaerts-Migration — Migrationen sind
-- unveraenderlich): die fuenf Constraints und den Index droppen. Geloeschte
-- Waisen kommen nicht zurueck; sie waren keinem Mandanten mehr zuzuordnen,
-- Passagen sind ohnehin aus der aktiven Version regenerierbar.
--
-- Idempotent (Runner-Vertrag) und schema-aware (unqualifizierte Namen,
-- current_schema()): DELETE ist nach dem ersten Lauf leer, FK via
-- pg_constraint-Guard, Index via IF NOT EXISTS.

-- (1) Bestand ---------------------------------------------------------------------
DELETE FROM kb_node n
 WHERE NOT EXISTS (SELECT 1 FROM workspace w WHERE w.id = n.workspace_id);

DELETE FROM kb_edge e
 WHERE NOT EXISTS (SELECT 1 FROM workspace w WHERE w.id = e.workspace_id);

DELETE FROM kb_edge_evidence v
 WHERE NOT EXISTS (SELECT 1 FROM workspace w WHERE w.id = v.workspace_id);

DELETE FROM kb_conflict c
 WHERE NOT EXISTS (SELECT 1 FROM workspace w WHERE w.id = c.workspace_id);

DELETE FROM content_chunk c
 WHERE NOT EXISTS (SELECT 1 FROM workspace w WHERE w.id = c.workspace_id);

-- (2) Fremdschluessel -------------------------------------------------------------
DO $$
DECLARE
    tname text;
BEGIN
    FOREACH tname IN ARRAY ARRAY['kb_node', 'kb_edge', 'kb_edge_evidence',
                                 'kb_conflict', 'content_chunk']
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

-- (3) Cascade-Lookup fuer kb_conflict (bisher nur Teilindex) ---------------------
CREATE INDEX IF NOT EXISTS kb_conflict_workspace_id_idx
    ON kb_conflict (workspace_id);
