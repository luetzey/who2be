-- Migration 0054 — Feedback-Triage via append-only Resolution-Events (ADR-0038)
--
-- Triage pro Feedback-Eintrag, OHNE die append-only agent_feedback-Zeile zu
-- mutieren: jede Triage-Aktion ist ein eigenes Ereignis. Der „aktuelle" Status
-- eines Feedbacks = das juengste Resolution-Event (created_at DESC). So bleibt
-- das Kurations-Prinzip aus 0053 erhalten (kein UPDATE/DELETE durch die App).
--
-- `resolution` ∈ {addressed, in_progress, dismissed} (Erledigt / In Arbeit /
-- Ignoriert) — via CHECK eingegrenzt. `feedback_id` ist ein echter FK auf
-- agent_feedback(id) mit ON DELETE CASCADE (DSGVO-Purge des Feedbacks raeumt die
-- Resolutions mit). RLS strikt auf app.current_tenant (Muster 0037/0053).
--
-- Append-only: GRANT nur SELECT, INSERT an who2be_app (kein UPDATE/DELETE);
-- der Owner behaelt Vollzugriff. Idempotent (IF NOT EXISTS / DROP+CREATE /
-- pg_roles-Guard).

CREATE TABLE IF NOT EXISTS feedback_resolution (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL,
    feedback_id  uuid NOT NULL REFERENCES agent_feedback (id) ON DELETE CASCADE,
    -- addressed | in_progress | dismissed.
    resolution   text NOT NULL CHECK (resolution IN ('addressed', 'in_progress', 'dismissed')),
    actor_id     uuid,
    note         text,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS feedback_resolution_latest_idx
    ON feedback_resolution (workspace_id, feedback_id, created_at DESC);

-- RLS strikt auf app.current_tenant (Workspace-Isolation, Muster 0053).
DO $$
BEGIN
    EXECUTE 'ALTER TABLE feedback_resolution ENABLE ROW LEVEL SECURITY';
    EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON feedback_resolution';
    EXECUTE format(
        'CREATE POLICY tenant_isolation ON feedback_resolution '
        'USING (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid) '
        'WITH CHECK (workspace_id = NULLIF(current_setting(%L, true), %L)::uuid)',
        'app.current_tenant', '', 'app.current_tenant', ''
    );
END
$$;

-- Append-only: nur SELECT + INSERT fuer die Laufzeitrolle (kein UPDATE/DELETE).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT SELECT, INSERT ON feedback_resolution TO who2be_app;
    END IF;
END
$$;
