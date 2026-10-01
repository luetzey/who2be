# M1 — RLS fuer workspace, organization, status_history; mcp_usage strikt

Karte: t_8ed14f76 · Basis: origin/main 4421cde3 · ADR-0055 R3/R4

## Ziel (fertig heisst)

Die Laufzeitrolle `who2be_app` sieht und aendert bei gesetztem Mandanten auch
**ohne** App-`WHERE` keine fremden Zeilen in `workspace`, `organization`,
`status_history` und `mcp_usage`. Der Org-Purge laesst keine
`status_history`-Zeilen zurueck. Login (`/v1/me`), Token-Lookup und Webhook
laufen weiter.

## Entscheidungen (aus Audit-Fix-Vorschlag + ADR-0055, nicht neu getroffen)

| Tabelle | Policy (`tenant_isolation`) |
|---|---|
| `workspace` | permissiv nur wenn **beide** GUCs leer; sonst `id = tenant OR org_id = org` |
| `organization` | permissiv nur wenn beide GUCs leer; sonst `id = org` |
| `status_history` | strikt `workspace_id = tenant` |
| `mcp_usage` | strikt `org_id = org` (bisher permissiv-bei-unset, 0037) |

- `org_id = org` bei `workspace` ist noetig: `PgWorkspaceRepository.delete`
  zaehlt die Workspaces der Org unter dem Mandanten (Last-Workspace-Schutz).
- „Beide leer" statt „tenant leer": ein Pfad mit nur `tenant_scope(ws, None)`
  (OAuth-Agent-Anzeige) bleibt dadurch strikt.
- `status_history.workspace_id`: Backfill aus der Entity-Tabelle
  (`entity_type` = Tabellenname), danach BEFORE-INSERT-Trigger, der den Wert
  **immer** aus der Entity ableitet (explizites CASE, kein dynamisches SQL;
  SECURITY INVOKER, damit der Lookup unter RLS laeuft). Repos bleiben
  unveraendert (Muster 0035).
- FK `workspace_id → workspace(id) ON DELETE CASCADE`: Org-/Workspace-Purge
  raeumt den Statusverlauf ab (R4a).
- Spalte bleibt **nullable**: Altzeilen, deren Entity schon geloescht ist,
  lassen sich keinem Workspace zuordnen. Unter der strikten Policy sind sie fuer
  `who2be_app` unsichtbar. Ob sie geloescht werden, ist eine Owner-Frage
  (Audit-Journal), nicht Teil dieser Migration → im Handoff gemeldet.
- `oauth_client` bleibt global (Audit).

## Schritte

1. Migration `0092_rls_control_plane_tables.sql` (0091 = offener PR #744).
2. Neuer Test `test_rls_control_plane.py` (als `who2be_app`, eigenes Schema):
   Isolation ohne WHERE fuer workspace/organization/status_history/mcp_usage,
   Schreibversuch fremder Workspace, Trigger-Ableitung, Org-Purge ohne Reste.
3. API-Test als `who2be_app`: `/v1/me` Lazy-Seed, Token-Anlage + Aufruf per
   `w2b_`-Token, Status-Transition + Dashboard, Workspace anlegen/loeschen.
4. Bestehende Tests nachziehen: `test_rls_isolation.py` (Ausnahme `workspace`
   entfaellt), `test_audit_append_only.py` (Insert braucht echte Entity).
5. Stale Doku: Kommentar `core/security.py`, Docstring `dashboard_repository.py`.
6. Changelog-Fragment.
7. Rot-Probe: neue Tests gegen origin/main-Migrationen → rot; mit 0092 → gruen.
8. DoD aus CONTRIBUTING.md, Branch pushen, PR, Review anfordern.

## Stand

- [x] 1 Migration `0092_rls_control_plane_tables.sql`
- [x] 2 `test_rls_control_plane.py` (3 Tests)
- [x] 3 `test_rls_control_plane_api.py` (2 Tests, Pool als `who2be_app`)
- [x] 4 `test_rls_isolation.py` (Ausnahmeliste leer), `test_audit_append_only.py`
- [x] 5 Stale Doku: `core/security.py`, ADR-0055 §5 (R3/R4a geschlossen) + §7
- [x] 6 Changelog-Fragment `rls-control-plane-tables.security.md`
- [x] 7 Rot/Gruen-Probe:
  - ohne 0092: 3/3 rot (fremde Zeilen sichtbar; Purge laesst Zeile stehen)
  - mit 0092: 3/3 gruen
  - Gegenprobe API-Test: `organization` ohne Permissiv-Zweig → Login-Test rot (500)
- [x] 8 DoD gruen (2425 passed, Cov 92 %, 0 Skips), PR #747; Review offen

## Beobachtung ausserhalb des Scopes

Laeuft die bestehende Suite mit `APP_DATABASE_URL=who2be_app`, scheitern
`test_me.py::test_me_has_password_true_when_encrypted_password_set` und
`test_gdpr_export.py::test_gdpr_export_bundles_user_data` — **identisch auf
origin/main** (lesen `auth.users` direkt; Thema N1b, PR #744). Nicht durch
0092 verursacht.

## Auf Zuruf angenommen

- Migrationsnummer 0092: 0091 belegt der offene PR #744; die Luecke ist laut
  `test_migrations.py` zulaessig (Runner sortiert nach Name).

## Out of Scope

M2 (permissive Policies von api_token/org_member/…), FORCE RLS (M3),
Export/Import je Org, API-Isolationstests je Endpunkt (t_40307837).
