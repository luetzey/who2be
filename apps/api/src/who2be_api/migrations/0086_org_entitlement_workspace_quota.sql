-- Migration 0086 — Workspace-Deckel je Organisation (Issue #576)
-- Plan: .claude/plan/2026-09-22-2100_576-workspace-deckel-je-org.md
--
-- Neues Entitlement-Feld `workspace_quota`: Obergrenze fuer die ANZAHL der
-- Workspaces einer Organisation (`workspace`, gezaehlt per org_id). Bisher
-- bremste nur `@limiter.limit(write_limit)` die Anlage — 30 Anlagen pro Minute,
-- unbegrenzt lange.
--
-- Anders als die beiden Zwillinge deckelt dieses Feld kein Kontingent, sondern
-- dessen Vervielfachbarkeit: `storage_quota_bytes` (0084) und `token_quota`
-- (0085) zaehlen je Workspace, eine Org mit n Workspaces haette sonst n-mal das
-- Kontingent. Bei Pro sind das 5 x 10 GiB = 50 GiB maximale Speicherzusage.
--
-- Bewusst KEINE abgeleitete Groesse wie `Entitlement.entity_limit()`: jene
-- Ableitung kann nur „Free-Zahl oder unbegrenzt" ausdruecken, hier hat Pro
-- aber eine eigene endliche Zahl (5).
--
-- Die Spalte gehoert auf BEIDE Tabellen: `org_entitlement` ist die gelesene
-- SSoT (0030), `entitlement_history` das lueckenlose Journal derselben Felder
-- (0045, ADR-0031) — ein Feld nur in der SSoT waere im Journal unsichtbar und
-- der GoBD-Nachweis unvollstaendig.
--
-- NULL = unbegrenzt auf Modell-Ebene, identisch zur Semantik der uebrigen
-- Quota-Spalten. In der Cloud faellt `NULL` allerdings auf den Tarifwert
-- zurueck (`Entitlement.effective_workspace_quota`), sonst haette ein Downgrade
-- die Grenze aufgehoben statt sie durchzusetzen — dieselbe Konstruktion wie bei
-- `token_quota` (0085).
-- Bewusst KEIN Backfill: ein nachtraeglich gesetzter Deckel auf Bestandszeilen
-- waere eine stille Verschaerfung bestehender Vertraege (vgl. ADR-0028). Und er
-- waere hier ueberdies wirkungslos — das Gate greift ausschliesslich bei NEUEN
-- Anlagen, Bestand bleibt auch ueber der Grenze vollstaendig nutzbar.
--
-- `integer` reicht (5 bzw. 1); anders als bei `storage_quota_bytes` (0084)
-- gibt es hier keinen int4-Ueberlauf.
--
-- Idempotenz: ADD COLUMN IF NOT EXISTS; der CHECK wird nur angelegt, wenn er
-- fehlt (kein `ADD CONSTRAINT IF NOT EXISTS` in Postgres). Schema-aware
-- (unqualifiziert), Muster 0039.

ALTER TABLE org_entitlement
    ADD COLUMN IF NOT EXISTS workspace_quota integer;

ALTER TABLE entitlement_history
    ADD COLUMN IF NOT EXISTS workspace_quota integer;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'org_entitlement_workspace_quota_check'
          AND conrelid = 'org_entitlement'::regclass
    ) THEN
        ALTER TABLE org_entitlement
            ADD CONSTRAINT org_entitlement_workspace_quota_check
            CHECK (workspace_quota IS NULL OR workspace_quota >= 0);
    END IF;
END
$$;
