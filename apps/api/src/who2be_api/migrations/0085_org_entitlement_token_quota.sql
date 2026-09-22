-- Migration 0085 — Token-Quota je Workspace (Issue #538)
-- Plan: .claude/plan/2026-09-22-0100_538-token-quota-je-workspace.md
--
-- Neues Entitlement-Feld `token_quota`: Obergrenze fuer die ANZAHL nutzbarer
-- API-Tokens je Workspace (`api_token`, gezaehlt werden nur nicht widerrufene
-- und nicht abgelaufene Zeilen). Bisher bremste nur `@limiter.limit(write_limit)`
-- die Anlage — also 30 Anlagen pro Minute, unbegrenzt lange.
--
-- Bewusst KEINE abgeleitete Groesse wie `Entitlement.entity_limit()`: jene
-- Ableitung kann nur „Free-Zahl oder unbegrenzt" ausdruecken, hier hat Pro
-- aber eine eigene endliche Zahl (25).
--
-- Die Spalte gehoert auf BEIDE Tabellen: `org_entitlement` ist die gelesene
-- SSoT (0030), `entitlement_history` das lueckenlose Journal derselben Felder
-- (0045, ADR-0031) — ein Feld nur in der SSoT waere im Journal unsichtbar und
-- der GoBD-Nachweis unvollstaendig.
--
-- NULL = unbegrenzt, identisch zur Semantik der beiden MCP-Spalten. Damit sind
-- Bestandszeilen nach dieser Migration unveraendert unbegrenzt; die Grenze
-- entsteht erst durch den naechsten Entitlement-Write (Checkout/Webhook) bzw.
-- ueber `CLOUD_FREE_ENTITLEMENT` fuer Orgs ganz ohne persistierten Stand.
-- Bewusst KEIN Backfill: ein nachtraeglich gesetzter Deckel auf Bestandszeilen
-- waere eine stille Verschaerfung bestehender Vertraege (vgl. ADR-0028) — und
-- genau das Aussperren laufender Agenten, das der Issue ausschliesst.
--
-- `integer` reicht (25 bzw. 3); anders als bei `storage_quota_bytes` (0084)
-- gibt es hier keinen int4-Ueberlauf.
--
-- Idempotenz: ADD COLUMN IF NOT EXISTS; der CHECK wird nur angelegt, wenn er
-- fehlt (kein `ADD CONSTRAINT IF NOT EXISTS` in Postgres). Schema-aware
-- (unqualifiziert), Muster 0039.

ALTER TABLE org_entitlement
    ADD COLUMN IF NOT EXISTS token_quota integer;

ALTER TABLE entitlement_history
    ADD COLUMN IF NOT EXISTS token_quota integer;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'org_entitlement_token_quota_check'
          AND conrelid = 'org_entitlement'::regclass
    ) THEN
        ALTER TABLE org_entitlement
            ADD CONSTRAINT org_entitlement_token_quota_check
            CHECK (token_quota IS NULL OR token_quota >= 0);
    END IF;
END
$$;
