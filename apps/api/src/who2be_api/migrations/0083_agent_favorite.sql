-- 0083 — Persoenliche Agent-Favoriten (Issue #427).
--
-- Ein Favorit ist ein privates User-Datum, kein Workspace-Aggregat: zwei
-- Mitglieder desselben Workspace sehen unterschiedliche Sterne. Deshalb eine
-- eigene Tabelle statt einer `is_pinned`-Spalte auf `agent` (die waere
-- workspace-weit) und statt `localStorage` (das ueberlebt keinen
-- Geraetewechsel).
--
-- `workspace_id` ist denormalisiert mitgefuehrt, obwohl es ueber `agent`
-- erreichbar waere: die RLS-Policy braucht die Spalte auf der Zeile selbst
-- (Muster 0066/0070/0079), sonst muesste jede Policy-Auswertung joinen.
--
-- KEIN FK auf den User: keine Tabelle im Schema referenziert den GoTrue-User
-- (`0007_workspace_member.sql`, `0049_oauth_connector.sql` tragen `user_id`
-- ebenfalls ohne REFERENCES). Die Bereinigung bei Konto-Loeschung laeuft
-- deshalb nicht per FK, sondern explizit in `purge_account_data`
-- (`repositories/account_repository.py`, Muster `oauth_authorization_code`).
CREATE TABLE IF NOT EXISTS agent_favorite (
    workspace_id uuid NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    agent_id uuid NOT NULL REFERENCES agent(id) ON DELETE CASCADE,
    user_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (agent_id, user_id)
);

-- Trage-Query der Agents-Seite: „welche Agenten hat DIESER User in DIESEM
-- Workspace markiert". Der PK (agent_id, user_id) deckt sie nicht ab, weil er
-- mit agent_id fuehrt.
CREATE INDEX IF NOT EXISTS agent_favorite_workspace_user_idx
    ON agent_favorite (workspace_id, user_id);

-- RLS strikt auf app.current_tenant (Workspace-Isolation, Muster 0066/0070/0079).
DO $$
BEGIN
    EXECUTE 'ALTER TABLE agent_favorite ENABLE ROW LEVEL SECURITY';
    EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON agent_favorite';
    EXECUTE format(
        'CREATE POLICY tenant_isolation ON agent_favorite '
        'USING (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid) '
        'WITH CHECK (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid)',
        'app.current_tenant', '', 'app.current_tenant', ''
    );
END
$$;

-- SELECT/INSERT/DELETE, kein UPDATE: ein Favorit wird gesetzt oder entfernt,
-- nie veraendert (der Toggle ist INSERT bzw. DELETE, s. `agent_repository`).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT SELECT, INSERT, DELETE ON agent_favorite TO who2be_app;
    END IF;
END
$$;
