-- Migration 0043 — Entitlement-Schreibquellen + Override-Audit (ADR-0028)
--
-- Schliesst die Herkunfts-Taxonomie der Org-Entitlements per CHECK und ergaenzt
-- Audit-Felder fuer den befristeten `manual_override`:
--   * mollie / cloud           — Cloud-Billing-Dienst (Pull bzw. generischer Webhook)
--   * manual_override          — Cloud-Ops-Override (befristet + auditiert)
--   * signed_license           — On-Prem (resolved live aus K_pub-Token, kein Write)
--
-- Leitprinzip: `org_entitlement` ist die einzige gelesene SSoT; sie wird nur von
-- klar benannten Quellen geschrieben, nie von der ausgelieferten Read-App.
--
-- Idempotenz: ADD COLUMN IF NOT EXISTS + guarded ADD CONSTRAINT (pg_constraint).

ALTER TABLE org_entitlement
    ADD COLUMN IF NOT EXISTS created_by uuid,
    ADD COLUMN IF NOT EXISTS reason text;

-- Legacy `source='manual'` (entferntes who2be-set-entitlement-CLI, G-3) auf den
-- neuen, befristeten Override heben — sonst scheitert der source-CHECK am
-- Altbestand. Sentinel-Urheber (nil-UUID) + 30 Tage Restlaufzeit, klar markiert.
-- In der Regel existieren keine solchen Zeilen (Dev-/Local-Tooling) → No-op.
UPDATE org_entitlement
   SET source = 'manual_override',
       created_by = COALESCE(created_by, '00000000-0000-0000-0000-000000000000'),
       reason = COALESCE(reason, 'migriert von Legacy source=manual (0043)'),
       expires_at = COALESCE(expires_at, now() + interval '30 days')
 WHERE source = 'manual';

-- Geschlossene Herkunfts-Taxonomie (ADR-0028).
DO $$
BEGIN
    -- conrelid-Scope (statt nur conname): pg_constraint.conname ist nur je
    -- Namespace eindeutig — ohne Tabellenbezug wuerde der Guard in isolierten
    -- Test-Schemata einen fremden, gleichnamigen Constraint faelschlich als
    -- „vorhanden" werten. `'org_entitlement'::regclass` loest die Tabelle im
    -- aktuellen search_path auf.
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'org_entitlement_source_check'
          AND conrelid = 'org_entitlement'::regclass
    ) THEN
        ALTER TABLE org_entitlement
            ADD CONSTRAINT org_entitlement_source_check
            CHECK (source IN ('mollie', 'cloud', 'manual_override', 'signed_license'));
    END IF;
END $$;

-- `manual_override` ist Pflicht-befristet (`expires_at`) + auditiert
-- (`created_by`). Der Ablauf greift ohne Sonderlogik ueber `is_active()`.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'org_entitlement_manual_override_check'
          AND conrelid = 'org_entitlement'::regclass
    ) THEN
        ALTER TABLE org_entitlement
            ADD CONSTRAINT org_entitlement_manual_override_check
            CHECK (
                source <> 'manual_override'
                OR (expires_at IS NOT NULL AND created_by IS NOT NULL)
            );
    END IF;
END $$;
