-- Migration 0106 — audit_log wird beim Loeschen von Workspace/Org anonymisiert
-- (Owner-Entscheidung E1a, Plan
-- .claude/plan/2026-10-10-1415_datenschutz-e1-1-audit-log-anonymisieren.md)
--
-- `audit_log` (0044) traegt `org_id`/`workspace_id` ohne Fremdschluessel. Nach
-- `DELETE /v1/workspaces/{id}` und nach dem Org-Purge blieben die Zeilen samt
-- Akteur (`actor_id`), Ziel (`target`, oft eine User-ID) und `detail`
-- (Token-Namen, Regel-Muster, Agent-IDs) stehen. E1a: „Beim Loeschen bleiben
-- Aktion, Zeitpunkt und Scope; Akteur, Ziel und personenbezogene Details
-- werden geleert." Die 12-Monats-Frist fuer den anonymen Rest ist ein eigenes
-- Paket (Worker-Routine); `anonymized_at` ist ihr Anker.
--
-- Bausteine:
--   (1) `audit_log.anonymized_at` — NULL = nicht anonymisiert.
--   (2) `w2b_audit_detail_allowlist()` — je Aktion die `detail`-Schluessel,
--       die keine Person und keinen Freitext tragen. SINGLE SOURCE OF TRUTH;
--       `test_audit_log_anonymization.py` verlangt fuer jede Aktion aus dem
--       Code einen Eintrag. Eine neue Aktion ergaenzt die Liste per neuer
--       Migration (`CREATE OR REPLACE FUNCTION`). Ohne Eintrag faellt `detail`
--       beim Anonymisieren ganz weg (fail-closed).
--   (3) `w2b_audit_anonymized_detail(action, detail)` — filtert auf (2).
--   (4) `w2b_audit_anonymize_scope()` — AFTER-DELETE-Trigger auf `workspace`
--       und `organization`: `actor_id` → Sentinel (NULL bleibt NULL, System-
--       Ereignis), `target` → NULL, `detail` → (3), `anonymized_at` → now().
--       `action`, `created_at`, `org_id`, `workspace_id` bleiben.
--   (5) Bestand: Zeilen, deren Workspace bzw. Org schon fehlt, einmalig gleich.
--
-- Trigger statt FK: E1a verlangt, dass der Scope bleibt — `ON DELETE SET NULL`
-- loeschte ihn, `CASCADE` die Zeile. Der Trigger greift auf jedem Loeschweg
-- (API-Workspace-Delete, Org-Purge, Personal-Org im Konto-Purge, kuenftige),
-- dasselbe Prinzip wie 0104/0105.
--
-- SECURITY DEFINER: der API-Workspace-Delete laeuft als `who2be_app`, und die
-- Rolle hat auf `audit_log` bewusst nur SELECT/INSERT (0044, append-only). Die
-- Trigger-Funktion laeuft daher als Owner. Haertung wie 0090/0093: fester
-- `search_path = pg_catalog, pg_temp`, Objekte schema-qualifiziert, EXECUTE
-- fuer PUBLIC entzogen. Eine Trigger-Funktion ist nicht direkt aufrufbar
-- (`RETURNS trigger`) — die App erhaelt kein allgemeines UPDATE-Recht.
--
-- Konto-Purge unveraendert: er setzt weiterhin nur `actor_id` des Users auf
-- denselben Sentinel (WP-D), Workspace und Ziel bestehen dort weiter.
--
-- Schema-aware (current_schema()) wie 0036/0090/0093. Idempotent: ADD COLUMN
-- IF NOT EXISTS, CREATE OR REPLACE, DROP TRIGGER IF EXISTS; (5) findet beim
-- zweiten Lauf nichts mehr (`anonymized_at IS NULL`).
--
-- Rueckweg (als eigene Vorwaerts-Migration): die zwei Trigger und drei
-- Funktionen droppen, `anonymized_at` droppen. Anonymisierte Werte kommen
-- nicht zurueck — das ist der Zweck.

ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS anonymized_at timestamptz;

DO $mig$
DECLARE
    app_schema text := current_schema();
    fn regprocedure;
BEGIN
    -- (2) Allowlist. Behalten wird nur Nicht-Personenbezogenes: Rollen,
    -- Fristen, Zaehler, Modell-Bezeichner, Matrix-Zellen. Weg sind Freitext
    -- (Token-Name, Regel-Muster/-Kategorie) und IDs (Agent, Regel, Client).
    EXECUTE format($ddl$
        CREATE OR REPLACE FUNCTION %1$I.w2b_audit_detail_allowlist()
        RETURNS jsonb
        LANGUAGE sql
        IMMUTABLE
        SET search_path = pg_catalog, pg_temp
        AS $fn$
            SELECT '{
                "account.deletion_requested": ["purge_after"],
                "agent.model_config_changed": ["model_provider", "model_name"],
                "case.deleted": [],
                "invitation.issued": ["role"],
                "invitation.revoked": [],
                "member.removed": ["role"],
                "member.role_changed": ["from", "to"],
                "memory.auto_policy.disabled": ["row", "origin"],
                "memory.auto_policy.enabled": ["row", "origin"],
                "memory.deleted": [],
                "memory.user_purged": ["count"],
                "org.soft_deleted": ["purge_after"],
                "token.issued": ["role", "via"],
                "token.renamed": [],
                "token.revoked": [],
                "token.role_capped": ["from_role", "to_role", "via"],
                "token.rotated": [],
                "workarea.rules_reapplied": []
            }'::jsonb
        $fn$
    $ddl$, app_schema);

    -- (3) Filter. Kein Objekt (Altbestand mit doppelt kodiertem JSON, 0081)
    -- ergibt `{}` — lieber nichts behalten als ungeprueften Text.
    EXECUTE format($ddl$
        CREATE OR REPLACE FUNCTION %1$I.w2b_audit_anonymized_detail(p_action text, p_detail jsonb)
        RETURNS jsonb
        LANGUAGE sql
        IMMUTABLE
        SET search_path = pg_catalog, pg_temp
        AS $fn$
            SELECT CASE
                WHEN jsonb_typeof(p_detail) IS DISTINCT FROM 'object' THEN '{}'::jsonb
                ELSE COALESCE(
                    (SELECT jsonb_object_agg(d.key, d.value)
                       FROM jsonb_each(p_detail) d
                      WHERE (%1$I.w2b_audit_detail_allowlist() -> p_action) ? d.key),
                    '{}'::jsonb)
            END
        $fn$
    $ddl$, app_schema);

    -- (4) Trigger-Funktion. `anonymized_at IS NULL` haelt Mehrfachlaeufe
    -- (Workspace-Trigger je Workspace, danach Org-Trigger) bei einem UPDATE
    -- je Zeile.
    EXECUTE format($ddl$
        CREATE OR REPLACE FUNCTION %1$I.w2b_audit_anonymize_scope()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, pg_temp
        AS $fn$
        BEGIN
            IF TG_TABLE_NAME = 'workspace' THEN
                UPDATE %1$I.audit_log a
                   SET actor_id = CASE WHEN a.actor_id IS NULL THEN NULL
                                       ELSE '00000000-0000-0000-0000-000000000000'::uuid END,
                       target = NULL,
                       detail = %1$I.w2b_audit_anonymized_detail(a.action, a.detail),
                       anonymized_at = now()
                 WHERE a.workspace_id = OLD.id AND a.anonymized_at IS NULL;
            ELSE
                UPDATE %1$I.audit_log a
                   SET actor_id = CASE WHEN a.actor_id IS NULL THEN NULL
                                       ELSE '00000000-0000-0000-0000-000000000000'::uuid END,
                       target = NULL,
                       detail = %1$I.w2b_audit_anonymized_detail(a.action, a.detail),
                       anonymized_at = now()
                 WHERE a.org_id = OLD.id AND a.anonymized_at IS NULL;
            END IF;
            RETURN NULL;
        END
        $fn$
    $ddl$, app_schema);

    fn := format('%I.w2b_audit_anonymize_scope()', app_schema)::regprocedure;
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC', fn);

    EXECUTE format('DROP TRIGGER IF EXISTS workspace_audit_anonymize ON %I.workspace', app_schema);
    EXECUTE format(
        'CREATE TRIGGER workspace_audit_anonymize AFTER DELETE ON %1$I.workspace '
        'FOR EACH ROW EXECUTE FUNCTION %1$I.w2b_audit_anonymize_scope()',
        app_schema
    );
    EXECUTE format('DROP TRIGGER IF EXISTS organization_audit_anonymize ON %I.organization', app_schema);
    EXECUTE format(
        'CREATE TRIGGER organization_audit_anonymize AFTER DELETE ON %1$I.organization '
        'FOR EACH ROW EXECUTE FUNCTION %1$I.w2b_audit_anonymize_scope()',
        app_schema
    );
END
$mig$;

-- (5) Bestand: Workspace bzw. Org schon geloescht.
UPDATE audit_log a
   SET actor_id = CASE WHEN a.actor_id IS NULL THEN NULL
                       ELSE '00000000-0000-0000-0000-000000000000'::uuid END,
       target = NULL,
       detail = w2b_audit_anonymized_detail(a.action, a.detail),
       anonymized_at = now()
 WHERE a.anonymized_at IS NULL
   AND (
        (a.workspace_id IS NOT NULL
         AND NOT EXISTS (SELECT 1 FROM workspace w WHERE w.id = a.workspace_id))
     OR (a.org_id IS NOT NULL
         AND NOT EXISTS (SELECT 1 FROM organization o WHERE o.id = a.org_id))
   );
