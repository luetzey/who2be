-- Migration 0079 — Zugriffslog: `agent_access_log` + Modell-Config am Agenten
-- (ADR-0047, User-Entscheidung 6)
-- Plan: .claude/plan/2026-08-13-1200_agent-workarea-knowledge-base.md
--
-- Lauf-Protokoll (Anforderung F) als AUTO-Zugriffslog: der Server loggt jeden
-- Agent-Zugriff (agent-gebundene Tokens) in den Read-/Write-Services selbst —
-- KEIN record_run-Selbstauskunfts-Tool, Vollstaendigkeit haengt nie an
-- Agenten-Disziplin. Dedupliziert pro (Agent, Element, Operation, Tag) ueber
-- den UNIQUE-Index; der Service schreibt `ON CONFLICT DO NOTHING`, `first_at`
-- traegt den ersten Zugriff des Tages. `sensitivity_at_access` snapshottet
-- der Server zum Zugriffszeitpunkt (spaetere Umstufung faelscht das Log nicht).
-- `ref_id` ist text (polymorph: uuid fuer artifact/node/table, sha256 fuer
-- blob) — daher bewusst ohne FK; Aufraeumen uebernimmt der Purge.
--
-- Append-only nach dem 0044-Muster: die Laufzeitrolle `who2be_app` bekommt
-- NUR SELECT + INSERT (kein UPDATE/DELETE) — das Log ist auf DB-Ebene
-- unveraenderlich. Der Owner (Migrations-/Purge-Job) behaelt Vollzugriff
-- (DSGVO-Erasure, Retention-Sweep).
--
-- Modell-Config am Agenten (User-Entscheidung 6): `model_provider`/
-- `model_name` sind BETREIBER-gepflegte Felder am Agenten (Agent-Update-Pfad,
-- nur Mensch). Grenze laut ADR-0047: das Modell gilt pro Agent-KONFIGURATION,
-- nicht pro Einzelaufruf (Who2Be ist kein Runtime-Host). Aenderungen werden
-- ab WP14 im `audit_log` protokolliert; die Betreiber-Query „welche Elemente
-- gingen je an einen externen Anbieter" joint Log × Agent-Config
-- (docs/compliance/, WP14).
--
-- Idempotenz: CREATE via IF NOT EXISTS; ALTER via ADD COLUMN IF NOT EXISTS;
-- Policy via DROP IF EXISTS + CREATE; GRANT idempotent; pg_roles-Guard
-- schuetzt On-Prem/Dev ohne who2be_app (Muster aus 0066/0070).

CREATE TABLE IF NOT EXISTS agent_access_log (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id          uuid NOT NULL,
    agent_id              uuid NOT NULL REFERENCES agent (id) ON DELETE CASCADE,
    -- Art des Elements: WorkArea-Artifact, KB-Node, Tabelle oder Blob.
    ref_kind              text NOT NULL
                          CHECK (ref_kind IN ('artifact', 'node', 'table', 'blob')),
    -- Polymorphe Element-Kennung (uuid bzw. sha256) — s. Kopfkommentar.
    ref_id                text NOT NULL,
    operation             text NOT NULL CHECK (operation IN ('read', 'write')),
    -- Server-Snapshot zum Zugriffszeitpunkt (nie rueckwirkend umgestuft).
    sensitivity_at_access text NOT NULL
                          CHECK (sensitivity_at_access IN ('general', 'sensitive')),
    -- Dedupe-Tag: ein Log-Eintrag pro Element+Operation und Kalendertag.
    access_date           date NOT NULL,
    first_at              timestamptz NOT NULL DEFAULT now()
);

-- Dedupe-Vertrag (Entscheidung 6): der Service schreibt ON CONFLICT DO
-- NOTHING gegen genau diesen Index.
CREATE UNIQUE INDEX IF NOT EXISTS agent_access_log_dedupe_uniq
    ON agent_access_log (agent_id, ref_kind, ref_id, operation, access_date);

-- Betreiber-/Compliance-Query: Zugriffe eines Workspaces im Zeitraum.
CREATE INDEX IF NOT EXISTS agent_access_log_workspace_date_idx
    ON agent_access_log (workspace_id, access_date);

-- Auswertung pro Agent (Betreiber-Query joint auf die Modell-Config).
CREATE INDEX IF NOT EXISTS agent_access_log_agent_id_idx
    ON agent_access_log (agent_id);

-- Betreiber-gepflegte Modell-Config (User-Entscheidung 6): gilt pro
-- Agent-Konfiguration, nicht pro Aufruf; Aenderung wird ab WP14 auditiert.
ALTER TABLE agent
    ADD COLUMN IF NOT EXISTS model_provider text,
    ADD COLUMN IF NOT EXISTS model_name text;

-- RLS strikt auf app.current_tenant (Workspace-Isolation, Muster 0066/0070).
DO $$
BEGIN
    EXECUTE 'ALTER TABLE agent_access_log ENABLE ROW LEVEL SECURITY';
    EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON agent_access_log';
    EXECUTE format(
        'CREATE POLICY tenant_isolation ON agent_access_log '
        'USING (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid) '
        'WITH CHECK (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid)',
        'app.current_tenant', '', 'app.current_tenant', ''
    );
END
$$;

-- Append-only-Grants (Muster 0044_audit_append_only): NUR SELECT + INSERT —
-- UPDATE/DELETE bleiben der App-Rolle DB-seitig verwehrt.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT SELECT, INSERT ON agent_access_log TO who2be_app;
    END IF;
END
$$;
