-- billing_0109 — Rechnungsdaten je Organisation (ADR-0061 §10, Paket R1).
--
-- Stammdaten, die eine Rechnung nach §14 UStG braucht: Kundentyp, Name bzw.
-- Firma, Rechnungsadresse, Land und optional die USt-IdNr. mit Pruefstand aus
-- VIES. Eine Zeile je Organisation (PK = org_id).
--
-- Billing-only (migrations/README.md): nur der Billing-Schreibdienst liest und
-- schreibt die Tabelle, sie existiert nur in der Cloud-Edition (ADR-0029).
--
-- Loeschung: `ON DELETE CASCADE` auf `organization`. Org-Purge und Konto-Purge
-- (Personal-Org) raeumen die Zeile damit ohne eigenen Schritt im Kern-Purge
-- (`repositories/account_repository.py#PgAccountPurgeRepository`). Das ist
-- Absicht und der Unterschied zur kuenftigen Rechnungszeile aus R2: dort gilt
-- die gesetzliche Aufbewahrung, hier nicht (ADR-0061 §9).
--
-- Die Feldregeln je Kundentyp stehen in `who2be_billing/billing_profile.py`
-- (Pydantic); die CHECKs hier sind nur die Untergrenze, die kein Schreibweg
-- unterlaufen darf.

CREATE TABLE IF NOT EXISTS billing_profile (
    org_id          uuid PRIMARY KEY REFERENCES organization (id) ON DELETE CASCADE,
    customer_type   text NOT NULL
                    CONSTRAINT billing_profile_customer_type_check
                    CHECK (customer_type IN ('business', 'consumer')),
    -- Vor- und Nachname getrennt, weil Mollie den Empfaenger `consumer` mit
    -- `givenName`/`familyName` erwartet (Create-Sales-Invoice-Referenz).
    given_name      text CONSTRAINT billing_profile_given_name_check
                    CHECK (given_name IS NULL OR length(given_name) BETWEEN 1 AND 100),
    family_name     text CONSTRAINT billing_profile_family_name_check
                    CHECK (family_name IS NULL OR length(family_name) BETWEEN 1 AND 100),
    company_name    text CONSTRAINT billing_profile_company_name_check
                    CHECK (company_name IS NULL OR length(company_name) BETWEEN 1 AND 200),
    street          text NOT NULL CONSTRAINT billing_profile_street_check
                    CHECK (length(street) BETWEEN 1 AND 200),
    postal_code     text NOT NULL CONSTRAINT billing_profile_postal_code_check
                    CHECK (length(postal_code) BETWEEN 1 AND 20),
    city            text NOT NULL CONSTRAINT billing_profile_city_check
                    CHECK (length(city) BETWEEN 1 AND 100),
    country         text NOT NULL CONSTRAINT billing_profile_country_check
                    CHECK (country ~ '^[A-Z]{2}$'),
    vat_id          text CONSTRAINT billing_profile_vat_id_check
                    CHECK (vat_id IS NULL OR vat_id ~ '^[A-Z]{2}[A-Z0-9]{2,13}$'),
    vat_status      text CONSTRAINT billing_profile_vat_status_check
                    CHECK (vat_status IN ('valid', 'invalid', 'unchecked')),
    vat_checked_at  timestamptz,
    updated_at      timestamptz NOT NULL DEFAULT now(),
    -- Kundentyp bestimmt die Pflichtfelder: Firma fuer B2B, Name fuer B2C;
    -- eine USt-IdNr. gibt es nur bei B2B und nie ohne Pruefstand.
    CONSTRAINT billing_profile_business_check
        CHECK (customer_type <> 'business' OR company_name IS NOT NULL),
    CONSTRAINT billing_profile_consumer_check
        CHECK (customer_type <> 'consumer'
               OR (given_name IS NOT NULL AND family_name IS NOT NULL AND vat_id IS NULL)),
    CONSTRAINT billing_profile_vat_status_pair_check
        CHECK ((vat_id IS NULL) = (vat_status IS NULL))
);

-- RLS wie `org_entitlement` (0037): permissiv bei ungesetztem `app.current_org`,
-- sonst strikt auf die eigene Org. Die Endpunkte laufen workspace-scoped (Org
-- gesetzt ⇒ strikt); der Mollie-Webhook aus R2 liest ohne Scope per explizitem
-- org_id. Idempotent: DROP POLICY IF EXISTS + CREATE.
ALTER TABLE billing_profile ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON billing_profile;
CREATE POLICY tenant_isolation ON billing_profile
    USING (NULLIF(current_setting('app.current_org', true), '') IS NULL
           OR org_id = NULLIF(current_setting('app.current_org', true), '')::uuid)
    WITH CHECK (NULLIF(current_setting('app.current_org', true), '') IS NULL
                OR org_id = NULLIF(current_setting('app.current_org', true), '')::uuid);

-- DML fuer die App-Rolle (Cloud). Kein DELETE: die Zeile faellt nur mit der
-- Organisation (Owner-Purge). pg_roles-Guard fuer Dev/Test ohne `who2be_app`.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'who2be_app') THEN
        GRANT SELECT, INSERT, UPDATE ON billing_profile TO who2be_app;
    END IF;
END
$$;
