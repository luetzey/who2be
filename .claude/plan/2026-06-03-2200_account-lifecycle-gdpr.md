# Track O — Account/Org-Lifecycle + GDPR-Export + Downgrade-Enforcement

**Status:** Work · **Datum:** 2026-06-03 · **Branch:** `feat/account-lifecycle-gdpr`
**Quelle:** `.claude/plan/2026-06-03-2030_cloud-launch-readiness.md` §3.2 (Downgrade-Vertrag)

## Entscheidungen
- **Soft-Delete + 30-Tage-Grace:** `organization.deleted_at`/`purge_after`;
  Account-Löschung über eigene Tabelle `account_deletion` (es gibt keine lokale
  User-Tabelle — Identität lebt in GoTrue `auth.users`).
- **GoTrue-Löschung:** läuft im **Hard-Purge** (nach Ablauf der Grace), nicht
  sofort — nur so ist das Grace-Fenster ein echtes Cooling-Off. Frontend meldet
  den User nach `DELETE /v1/me` clientseitig ab (`supabase.auth.signOut`).
- **Hard-Purge-Job:** CLI `who2be-purge` (Cron) → `purge_service.purge_expired`.
  Org-Purge = `DELETE FROM organization` (CASCADE räumt alles darunter).
- **GDPR-Export:** `GET /v1/gdpr/export` — iteriert die Workspaces des Users,
  betritt je Workspace `tenant_scope` (RLS-konform!) und sammelt das Bündel.
  Rate-limitiert (`write_limit`).
- **Downgrade-Enforcement (§3.2):** `Entitlement.entity_limit()` aus den
  Feature-Codes abgeleitet (Free = nur `core` → `FREE_ENTITY_QUOTA`; jeder
  Paid-Plan/On-Prem → unbegrenzt; inaktiv → Free-Limit). Gate
  `enforce_entity_quota` an den POST-Create-Routen (persona/playbook/resource/
  agent), **per Workspace** gezählt (RLS lässt im Scope nur den aktuellen
  Workspace sehen). Bestand bleibt lesbar; nur neue Über-Limit-Creates → 402.
  MCP-Quota greift bereits über `mcp_limit_service` (unverändert).

## Dateien
- Migration `0038_account_org_lifecycle.sql`
- `licensing/entitlement.py` (entity_quota + entity_limit)
- `services/entity_quota_service.py`, `services/account_lifecycle_service.py`,
  `services/gdpr_export_service.py`, `core/purge.py`
- `repositories/account_repository.py`, `repositories/entity_count_repository.py`
- `integrations/gotrue_admin.py`
- `routers/me.py`, `routers/organizations.py`, neuer `routers/gdpr.py`
- Filter `deleted_at IS NULL` in me/organization-Repos + Block in
  `get_current_workspace`
- Web: `AccountPage` (Export + Konto löschen), `OrgSettingsPage` (Org löschen),
  `api/client.ts` + `api/types.ts`

## DoD
ruff + mypy + pytest grün; Web lint/tsc/test/build grün; security-reviewer.
