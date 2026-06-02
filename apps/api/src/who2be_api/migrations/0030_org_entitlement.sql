-- Migration 0030 — org_entitlement (Track D, Plan §3.5)
-- Single Source of Truth der Nutzungsrechte pro Org. NUR der Cloud-Pfad
-- persistiert hier: der Billing-Webhook leitet das Entitlement aus den
-- Provider-Ereignissen ab und schreibt es; der Cloud-Read-Adapter liest es.
-- On-Prem nutzt diese Tabelle nicht (offline signierte Lizenzdatei, K_pub).
--
-- DB-Symmetrie (Plan §3.6): ein Schema fuer Cloud + On-Prem. RLS-Haertung ist
-- ein separater spaeterer Schritt (§5) — hier KEIN App-SQL-Umbau.

CREATE TABLE IF NOT EXISTS org_entitlement (
    org_id            uuid PRIMARY KEY REFERENCES organization (id) ON DELETE CASCADE,
    status            text NOT NULL DEFAULT 'active'
                          CHECK (status IN ('active', 'inactive')),
    -- Freigeschaltete Feature-Codes (aus Provider-Metadaten `license_policy`),
    -- als JSON-Array. Kein hartkodiertes Produkt→Feature-Mapping im Code.
    features          jsonb NOT NULL DEFAULT '[]'::jsonb,
    expires_at        timestamptz,
    -- NULL = unbegrenzt (z. B. ein Enterprise-Plan ohne MCP-Kontingent).
    mcp_monthly_quota integer CHECK (mcp_monthly_quota IS NULL OR mcp_monthly_quota >= 0),
    mcp_rate_per_min  integer CHECK (mcp_rate_per_min IS NULL OR mcp_rate_per_min >= 0),
    -- Herkunft des Stands: 'cloud' (Webhook) bzw. 'onprem' (Lizenzdatei).
    source            text NOT NULL DEFAULT 'cloud',
    -- Provider-seitige Referenz (z. B. Subscription-/Session-ID) fuer Audits.
    external_ref      text,
    updated_at        timestamptz NOT NULL DEFAULT now()
);
