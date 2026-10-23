-- billing_0111 — Rechnung je Zahlung (ADR-0061 §4, §7, §9; Paket R2a).
--
-- Mollie sperrt keine Duplikate: dieselbe Zahlung zweimal referenziert ergibt
-- zwei Rechnungen mit zwei Nummern (Testbericht P3b). Who2Be sichert deshalb
-- selbst ab, und zwar hier: `UNIQUE (payment_id)`. Der Webhook legt die Zeile
-- mit `INSERT … ON CONFLICT (payment_id) DO NOTHING` an; ein zweiter Ping oder
-- ein paralleler Lauf findet sie und legt keine zweite an.
--
-- Zweite Sperre: `post_started_at` wird atomar gesetzt, BEVOR Who2Be bei
-- Mollie POSTet. Wer es nicht setzen konnte, POSTet nicht. Steht es nach einem
-- Timeout noch, ist offen, ob Mollie die Rechnung angelegt hat; dann sucht der
-- Worker (R2b) zuerst ueber die List-API, statt neu zu POSTen.
--
-- Aufbewahrung: `org_id` ist bewusst KEIN Fremdschluessel auf `organization`
-- (wie `entitlement_history`, Migration 0045). Ausgestellte Rechnungen bleiben
-- trotz Org- oder Konto-Purge bis zum Ende der Frist (§14b UStG, §147 AO,
-- Art. 17 Abs. 3 lit. b DSGVO). Ein FK mit CASCADE braeche die Aufbewahrung,
-- einer ohne blockierte den Purge.
--
-- Unveraenderbarkeit (ADR-0061 §7): die Laufzeitrolle darf Zeilen anlegen und
-- den Status nur nach vorn setzen. Mollie-ID, Rechnungsnummer, Ablageort und
-- SHA-256 des PDF sind nach dem ersten Setzen fest; Steuerangaben (Schalter,
-- Satz, Memo), Betrag, Zeitraum, Plan, Kunde und Ausstellungszeit sind ab
-- Status 'issued' fest (Trigger unten). Kein
-- DELETE-Grant: loeschen darf nur die Owner-Rolle nach Ablauf der Frist.
--
-- Billing-only (migrations/README.md), nur Cloud (ADR-0029). Idempotent.

CREATE TABLE IF NOT EXISTS billing_invoice (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- KEIN FK auf organization (Begruendung oben).
    org_id            uuid NOT NULL,
    payment_id        text NOT NULL
                      CONSTRAINT billing_invoice_payment_id_key UNIQUE
                      CONSTRAINT billing_invoice_payment_id_check
                      CHECK (payment_id ~ '^tr_[A-Za-z0-9]{1,64}$'),
    customer_id       text CONSTRAINT billing_invoice_customer_id_check
                      CHECK (customer_id IS NULL OR customer_id ~ '^cst_[A-Za-z0-9]{1,64}$'),
    plan_code         text NOT NULL,
    -- Bezahlter Betrag laut Mollie. Die Rechnung muss ihn treffen, sonst bleibt
    -- sie zurueckgehalten (keine Rechnung ueber einen anderen Betrag).
    amount_value      numeric(10, 2),
    period_start      date NOT NULL,
    period_end        date NOT NULL,
    status            text NOT NULL DEFAULT 'pending'
                      CONSTRAINT billing_invoice_status_check
                      CHECK (status IN ('pending', 'issued', 'archived', 'failed')),
    post_started_at   timestamptz,
    mollie_invoice_id text CONSTRAINT billing_invoice_mollie_id_check
                      CHECK (mollie_invoice_id IS NULL
                             OR mollie_invoice_id ~ '^invoice_[A-Za-z0-9]{1,64}$'),
    invoice_number    text CONSTRAINT billing_invoice_number_check
                      CHECK (invoice_number IS NULL
                             OR invoice_number ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$'),
    -- Mit welchen Schalterwerten die Rechnung entstand (ADR-0061 §5: ein
    -- Wechsel wirkt nur nach vorn).
    tax_mode          text CONSTRAINT billing_invoice_tax_mode_check
                      CHECK (tax_mode IS NULL OR tax_mode IN ('regular', 'small_business')),
    price_basis       text CONSTRAINT billing_invoice_price_basis_check
                      CHECK (price_basis IS NULL OR price_basis IN ('net', 'gross')),
    vat_rate          numeric(5, 2),
    memo_key          text,
    issued_at         timestamptz,
    pdf_key           text,
    pdf_sha256        text CONSTRAINT billing_invoice_pdf_sha256_check
                      CHECK (pdf_sha256 IS NULL OR pdf_sha256 ~ '^[0-9a-f]{64}$'),
    archived_at       timestamptz,
    attempts          integer NOT NULL DEFAULT 0,
    last_error        text CONSTRAINT billing_invoice_last_error_check
                      CHECK (last_error IS NULL OR length(last_error) <= 500),
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT billing_invoice_period_check CHECK (period_end >= period_start),
    CONSTRAINT billing_invoice_issued_check
        CHECK (status NOT IN ('issued', 'archived')
               OR (mollie_invoice_id IS NOT NULL AND invoice_number IS NOT NULL
                   AND issued_at IS NOT NULL)),
    CONSTRAINT billing_invoice_archived_check
        CHECK (status <> 'archived' OR (pdf_key IS NOT NULL AND pdf_sha256 IS NOT NULL))
);

-- Offene Zeilen fuer den Worker (R2b) und die Betreiber-Sicht.
CREATE INDEX IF NOT EXISTS billing_invoice_open_idx
    ON billing_invoice (status, created_at) WHERE status IN ('pending', 'issued');
CREATE INDEX IF NOT EXISTS billing_invoice_org_idx
    ON billing_invoice (org_id, created_at DESC);

-- Status nur nach vorn, belegte Felder fest.
CREATE OR REPLACE FUNCTION billing_invoice_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    old_rank integer := CASE OLD.status WHEN 'pending' THEN 0 WHEN 'issued' THEN 1 ELSE 2 END;
    new_rank integer := CASE NEW.status WHEN 'pending' THEN 0 WHEN 'issued' THEN 1 ELSE 2 END;
BEGIN
    IF NEW.org_id <> OLD.org_id OR NEW.payment_id <> OLD.payment_id THEN
        RAISE EXCEPTION 'billing_invoice: org_id und payment_id sind unveraenderlich';
    END IF;
    IF OLD.status IN ('archived', 'failed') AND NEW.status <> OLD.status THEN
        RAISE EXCEPTION 'billing_invoice: Status % ist endgueltig', OLD.status;
    END IF;
    IF new_rank < old_rank THEN
        RAISE EXCEPTION 'billing_invoice: Status darf nicht zurueck (% -> %)',
            OLD.status, NEW.status;
    END IF;
    IF (OLD.mollie_invoice_id IS NOT NULL
            AND NEW.mollie_invoice_id IS DISTINCT FROM OLD.mollie_invoice_id)
       OR (OLD.invoice_number IS NOT NULL
            AND NEW.invoice_number IS DISTINCT FROM OLD.invoice_number)
       OR (OLD.pdf_key IS NOT NULL AND NEW.pdf_key IS DISTINCT FROM OLD.pdf_key)
       OR (OLD.pdf_sha256 IS NOT NULL AND NEW.pdf_sha256 IS DISTINCT FROM OLD.pdf_sha256)
    THEN
        RAISE EXCEPTION 'billing_invoice: Rechnung und PDF sind nach dem Setzen unveraenderlich';
    END IF;
    -- Ab 'issued' ist die Rechnung ausgestellt: Schalterwerte, Steuerfall,
    -- Betrag, Zeitraum und Ausstellungszeit (steuert das Archivjahr) sind fest.
    -- Nur eine pending-Zeile darf der Worker (R2b) noch korrigieren.
    IF OLD.status <> 'pending' AND (
           NEW.tax_mode     IS DISTINCT FROM OLD.tax_mode
        OR NEW.price_basis  IS DISTINCT FROM OLD.price_basis
        OR NEW.vat_rate     IS DISTINCT FROM OLD.vat_rate
        OR NEW.memo_key     IS DISTINCT FROM OLD.memo_key
        OR NEW.issued_at    IS DISTINCT FROM OLD.issued_at
        OR NEW.amount_value IS DISTINCT FROM OLD.amount_value
        OR NEW.period_start IS DISTINCT FROM OLD.period_start
        OR NEW.period_end   IS DISTINCT FROM OLD.period_end
        OR NEW.plan_code    IS DISTINCT FROM OLD.plan_code
        OR NEW.customer_id  IS DISTINCT FROM OLD.customer_id)
    THEN
        RAISE EXCEPTION 'billing_invoice: Steuer- und Rechnungsangaben sind ab Status % unveraenderlich',
            OLD.status;
    END IF;
    NEW.updated_at := now();
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS billing_invoice_guard ON billing_invoice;
CREATE TRIGGER billing_invoice_guard
    BEFORE UPDATE ON billing_invoice
    FOR EACH ROW EXECUTE FUNCTION billing_invoice_guard();

-- RLS wie `entitlement_history` (0045): permissiv bei ungesetztem
-- `app.current_org` (der Webhook laeuft ohne Org-Scope), sonst strikt.
ALTER TABLE billing_invoice ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON billing_invoice;
CREATE POLICY tenant_isolation ON billing_invoice
    USING (NULLIF(current_setting('app.current_org', true), '') IS NULL
           OR org_id = NULLIF(current_setting('app.current_org', true), '')::uuid)
    WITH CHECK (NULLIF(current_setting('app.current_org', true), '') IS NULL
                OR org_id = NULLIF(current_setting('app.current_org', true), '')::uuid);

-- Kein DELETE fuer die App-Rolle. pg_roles-Guard fuer Dev/Test ohne `who2be_app`.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT SELECT, INSERT, UPDATE ON billing_invoice TO who2be_app;
    END IF;
END
$$;
