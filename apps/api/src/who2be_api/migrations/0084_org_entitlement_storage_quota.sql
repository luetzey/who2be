-- Migration 0084 — Speicher-Quota je Org (Issue #536)
-- Plan: .claude/plan/2026-09-21-2230_536-speicher-quota-je-org.md
--
-- Neues Entitlement-Feld `storage_quota_bytes`: Obergrenze fuer die SUMME der
-- abgelegten Blob-Bytes (`wa_blob.size_bytes`, Migration 0075) — bisher gab es
-- nur `WHO2BE_INGEST_MAX_BYTES`, und das gilt pro Datei, nicht in Summe.
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
-- waere eine stille Verschaerfung bestehender Vertraege (vgl. ADR-0028).
--
-- `bigint` statt `integer`: 10 GiB (10737418240) passt nicht in int4.
--
-- Idempotenz: ADD COLUMN IF NOT EXISTS; der CHECK wird nur angelegt, wenn er
-- fehlt (kein `ADD CONSTRAINT IF NOT EXISTS` in Postgres). Schema-aware
-- (unqualifiziert), Muster 0039.

ALTER TABLE org_entitlement
    ADD COLUMN IF NOT EXISTS storage_quota_bytes bigint;

ALTER TABLE entitlement_history
    ADD COLUMN IF NOT EXISTS storage_quota_bytes bigint;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'org_entitlement_storage_quota_bytes_check'
          AND conrelid = 'org_entitlement'::regclass
    ) THEN
        ALTER TABLE org_entitlement
            ADD CONSTRAINT org_entitlement_storage_quota_bytes_check
            CHECK (storage_quota_bytes IS NULL OR storage_quota_bytes >= 0);
    END IF;
END
$$;
