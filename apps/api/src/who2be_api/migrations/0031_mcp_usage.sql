-- Migration 0031 — mcp_usage (Track D, Plan §3.5, Entscheidung #9)
-- Monats-Kontingent pro Org fuer agent-facing MCP-Reads. Pro (Org, Periode)
-- ein Zaehler; die Periode ist 'YYYYMM' (UTC). Der Reset ist implizit: ein
-- neuer Monat = ein neuer Zeilenschluessel, ab 0. Nur der Cloud-Pfad inkrementiert
-- (das Limit-Gate ist allein unter is_cloud() aktiv); On-Prem ist unbegrenzt.

CREATE TABLE IF NOT EXISTS mcp_usage (
    org_id     uuid NOT NULL REFERENCES organization (id) ON DELETE CASCADE,
    period     text NOT NULL,  -- 'YYYYMM' (UTC)
    count      integer NOT NULL DEFAULT 0 CHECK (count >= 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id, period)
);
