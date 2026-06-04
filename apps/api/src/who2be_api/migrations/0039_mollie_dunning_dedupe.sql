-- Migration 0039 — Mollie-Haertung: Webhook-Dedupe + Dunning-Grace (Track P, Plan §3.2)
-- Plan: .claude/plan/2026-06-03-2030_cloud-launch-readiness.md (Track P)
--
-- Renumber-Hinweis: lief vorab als 0038, kollidierte mit `0038_account_org_lifecycle.sql`
-- aus dem parallelen Track O. Beide Files sind idempotent (CREATE TABLE/ADD COLUMN
-- IF NOT EXISTS, Grants pg_roles-geguarded) und voellig unabhaengig — die
-- Umbenennung ist gefahrlos und reine Reihenfolge. Migrationen werden per Glob
-- entdeckt und alphabetisch angewendet; kein Code referenziert den Dateinamen.
--
-- Zwei unabhaengige Bausteine der Mollie-Haertung:
--
-- 1) `processed_webhook_event` — Idempotenz-/Dedupe-Ledger. Mollie liefert
--    denselben Ping bei Netz-/Timeout-Retries mehrfach; ohne Dedupe wuerde eine
--    bezahlte Erstzahlung u. U. zwei Subscriptions anlegen. Der Webhook-Pfad
--    beansprucht jede (provider, event_id) genau einmal (UNIQUE) — der erste
--    Claim verarbeitet, jeder weitere ist No-Op.
--
-- 2) `org_entitlement.grace_until` — Dunning-Signal. Eine fehlgeschlagene
--    Folgezahlung setzt eine Grace-Period statt sofort auf Free zu degradieren:
--    der gebuchte Tier bleibt aktiv (Banner via Entitlement-Read), erst nach
--    Ablauf greift die Sperre (ueber `expires_at`, das auf dieselbe Frist gesetzt
--    wird — kein zusaetzlicher Job noetig).
--
-- RLS: `processed_webhook_event` traegt keine Mandanten-Spalte (kein org_id/
-- workspace_id) und wird ausschliesslich vom anonymen Billing-Webhook geschrieben.
-- Es ist daher — wie `api_token`/`organization` — bewusst NICHT in der
-- tenant_isolation-Policy (0037); nur die Grants an `who2be_app` werden gesetzt.
--
-- Idempotenz: CREATE TABLE IF NOT EXISTS + ADD COLUMN IF NOT EXISTS; GRANT ist
-- von Natur aus idempotent. Schema-aware (unqualifiziert).

-- 1) Dedupe-Ledger fuer Provider-Webhooks.
CREATE TABLE IF NOT EXISTS processed_webhook_event (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- Zahlungsanbieter ('mollie'); haelt den Keyspace getrennt, falls weitere
    -- Provider hinzukommen.
    provider    text NOT NULL,
    -- Provider-seitige Ereignis-/Zahlungs-ID (Mollie: Payment-`id`).
    event_id    text NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider, event_id)
);

-- 2) Dunning-Grace auf dem Org-Entitlement. NULL = keine laufende Grace-Period.
ALTER TABLE org_entitlement
    ADD COLUMN IF NOT EXISTS grace_until timestamptz;

-- Grants fuer die Laufzeit-Rolle (Cloud). Der Webhook braucht INSERT (Claim),
-- SELECT sowie DELETE — Letzteres ausschliesslich fuer die gezielte Freigabe des
-- eigenen, gerade gescheiterten Claims (Retry-Sicherheit), kein Massen-Purge.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT SELECT, INSERT, DELETE ON processed_webhook_event TO who2be_app;
    END IF;
END
$$;
