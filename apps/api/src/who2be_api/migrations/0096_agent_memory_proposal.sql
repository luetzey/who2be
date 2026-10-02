-- Migration 0096 — Aenderungs- und Loeschvorschlaege von Agenten
-- `agent_memory_proposal`, Event `auto_revoked` (ADR-0053 3.1.2, 3.1.4, 6.4.1;
-- Lernschleife Phase C, Paket C3a)
--
-- Ein Agent darf einen bestehenden Eintrag nicht selbst aendern oder loeschen,
-- sondern nur vorschlagen (3.1.4). Vorschlaege werden NIE automatisch
-- angenommen, auch nicht unter `memory_mode=auto` (Matrix 4.2, Zeile
-- „Aenderung/Loeschung“) — dafuer gibt es hier bewusst keine Spalte, die
-- eine automatische Annahme ausdruecken koennte. Annahme durch einen Menschen
-- schreibt `proposal_accepted` plus `edited` bzw. loescht den Eintrag.
--
-- Spalten (3.1.4):
-- - `action` `change|delete`; `new_fact` genau bei `change` (DB-CHECK), Laenge
--   wie `agent_memory.fact` (300). Die Waechter von `save_memory` (Injection,
--   Secret-Scan) laufen im Service, nicht hier.
-- - `reason` Pflicht, 1..200 Zeichen.
-- - `status` `pending|accepted|rejected`; `decided_by`/`decided_at` genau dann
--   gesetzt, wenn entschieden (DB-CHECK).
-- - `decided_by` ohne FK: Nutzer leben in der Auth-Schicht (Muster
--   `agent_memory.confirmed_by`, 0091).
--
-- Grants: die App-Rolle darf nur SELECT, INSERT und UPDATE auf genau den
-- Entscheidungs-Spalten (`status`, `decided_by`, `decided_at`) — der Vorschlag
-- selbst (Text, Begruendung, Agent, Ziel) ist nach dem Anlegen unveraenderlich
-- (3.1.4 „UPDATE nur auf status“; die beiden Begleitspalten der Entscheidung
-- gehoeren dazu). Kein DELETE: ein Vorschlag faellt nur per Cascade mit
-- seinem Eintrag, Agenten oder Workspace.
--
-- Bindung: Composite-FKs auf `(workspace_id, id)` von Eintrag und Agent —
-- ein Vorschlag haengt immer an Eintrag und Agent DESSELBEN Workspace (Muster
-- 0089/0091). Faellt der Eintrag (Hard-Delete, auch per Annahme eines
-- Loeschvorschlags), fallen seine Vorschlaege mit. Faellt der vorschlagende
-- Agent, fallen seine Vorschlaege ebenfalls: ein offener Vorschlag ohne
-- Absender ist nicht mehr nachvollziehbar, entschiedene stehen in der
-- Historie des Eintrags (`proposal_accepted`/`proposal_rejected`).
--
-- Event `auto_revoked` (6.4.1, Not-Aus): erweitert den Event-CHECK aus 0091.
--
-- Rueckweg (eigene Vorwaerts-Migration): Tabelle droppen; Event-CHECK ohne
-- `auto_revoked`, vorher solche Events loeschen (die Historie ist
-- append-only, das erledigt eine Owner-Migration).
--
-- Idempotenz: CREATE TABLE/INDEX IF NOT EXISTS; Constraint via DROP IF EXISTS
-- + ADD; Policy via DROP IF EXISTS + CREATE; GRANT idempotent; pg_roles-Guard
-- fuer On-Prem/Dev.

-- --- Historie: Event `auto_revoked` ---------------------------------------------

ALTER TABLE agent_memory_event DROP CONSTRAINT IF EXISTS agent_memory_event_event_check;
ALTER TABLE agent_memory_event ADD CONSTRAINT agent_memory_event_event_check
    CHECK (event IN (
        'created', 'auto_activated', 'approved', 'rejected', 'edited',
        'confirmed', 'expired', 'reactivated', 'change_proposed',
        'delete_proposed', 'proposal_accepted', 'proposal_rejected',
        'rolled_back', 'converted', 'merged', 'auto_revoked'));

-- --- Vorschlaege (3.1.4) --------------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_memory_proposal (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES workspace (id) ON DELETE CASCADE,
    memory_id    uuid NOT NULL,
    agent_id     uuid NOT NULL,
    action       text NOT NULL CHECK (action IN ('change', 'delete')),
    new_fact     text CHECK (char_length(new_fact) BETWEEN 1 AND 300),
    reason       text NOT NULL CHECK (char_length(reason) BETWEEN 1 AND 200),
    status       text NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'accepted', 'rejected')),
    decided_by   uuid,
    decided_at   timestamptz,
    created_at   timestamptz NOT NULL DEFAULT now(),
    -- `new_fact` genau bei `change`.
    CONSTRAINT agent_memory_proposal_new_fact_action_check
        CHECK ((action = 'change') = (new_fact IS NOT NULL)),
    -- Entscheidungs-Spalten genau dann, wenn entschieden.
    CONSTRAINT agent_memory_proposal_decided_check
        CHECK ((status = 'pending') = (decided_at IS NULL)
               AND (status = 'pending' OR decided_by IS NOT NULL)),
    CONSTRAINT agent_memory_proposal_memory_fkey
        FOREIGN KEY (workspace_id, memory_id)
        REFERENCES agent_memory (workspace_id, id) ON DELETE CASCADE,
    CONSTRAINT agent_memory_proposal_agent_fkey
        FOREIGN KEY (workspace_id, agent_id)
        REFERENCES agent (workspace_id, id) ON DELETE CASCADE
);

-- Offene Vorschlaege je Eintrag (Entscheiden, Anzeige an der Historie).
CREATE INDEX IF NOT EXISTS agent_memory_proposal_memory_idx
    ON agent_memory_proposal (workspace_id, memory_id, created_at);

-- Liste je Agent und Status (`GET /agents/{agent_id}/memory-proposals`).
CREATE INDEX IF NOT EXISTS agent_memory_proposal_agent_idx
    ON agent_memory_proposal (workspace_id, agent_id, status, created_at DESC);

-- RLS strikt auf app.current_tenant (Muster 0066/0089/0091).
DO $$
BEGIN
    EXECUTE 'ALTER TABLE agent_memory_proposal ENABLE ROW LEVEL SECURITY';
    EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON agent_memory_proposal';
    EXECUTE format(
        'CREATE POLICY tenant_isolation ON agent_memory_proposal '
        'USING (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid) '
        'WITH CHECK (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid)',
        'app.current_tenant', '', 'app.current_tenant', ''
    );
END
$$;

-- Vorschlag unveraenderlich, nur die Entscheidung ist schreibbar.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT SELECT, INSERT ON agent_memory_proposal TO who2be_app;
        GRANT UPDATE (status, decided_by, decided_at) ON agent_memory_proposal TO who2be_app;
    END IF;
END
$$;
