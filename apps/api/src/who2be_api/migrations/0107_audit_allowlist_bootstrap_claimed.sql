-- Migration 0107 — Audit-Allowlist um `org.bootstrap_claimed` erweitert
--
-- Der erste Login des Bootstrap-Admins uebernimmt die geseedete Bootstrap-Org
-- (`services/bootstrap_service.py#claim_bootstrap_org`) und schreibt dabei je
-- Workspace eine `audit_log`-Zeile `org.bootstrap_claimed` (ADR-0031: Admin-
-- und Security-Events gehoeren ins Audit-Log). Jede Aktion braucht einen
-- Eintrag in `w2b_audit_detail_allowlist()` (0106, Single Source of Truth;
-- Guard `test_audit_log_anonymization.py::test_every_audit_action_has_an_allowlist_entry`).
--
-- Die neue Aktion traegt kein `detail` — Akteur und Ziel stehen in `actor_id`
-- und `target`, die beim Anonymisieren ohnehin geleert werden. Der Eintrag ist
-- deshalb `[]`.
--
-- Einzige Aenderung gegenueber 0106: die Zeile `"org.bootstrap_claimed": []`.
-- Filter, Trigger und Bestand aus 0106 bleiben unberuehrt; der Filter ruft die
-- Allowlist zur Laufzeit auf und sieht den neuen Eintrag sofort.
--
-- Schema-aware (current_schema()) wie 0106. Idempotent: CREATE OR REPLACE.
-- Rueckweg (als eigene Vorwaerts-Migration): die Funktion mit der Liste aus
-- 0106 erneut anlegen — erst nachdem die Aktion aus dem Code entfernt ist.

DO $mig$
DECLARE
    app_schema text := current_schema();
BEGIN
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
                "org.bootstrap_claimed": [],
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
END
$mig$;
