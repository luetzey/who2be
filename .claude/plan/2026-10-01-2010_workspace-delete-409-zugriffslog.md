# Workspace-Delete: 409 statt 500 bei vorhandenem Zugriffslog

Board: t_19169bdd (Befund aus dem Isolationstest t_40307837, PR #749)

## Ausgangslage

`WorkspaceRepository.delete` loescht zuerst `DELETE FROM agent WHERE
workspace_id = $1`. Seit Migration 0080 ist `agent_access_log.agent_id`
`ON DELETE NO ACTION` (ADR-0047 H5). Hat ein Agent des Workspaces je
protokollierte Zugriffe, scheitert der Delete mit `ForeignKeyViolationError`
und die Route antwortet 500.

## Weiche (Owner-Entscheidung 2026-10-01, Frage 4 = a)

409 mit Hinweis auf den Retention-/Purge-Pfad, wie beim Agent-Delete.
Kein Soft-Delete, kein Mitloeschen der Log-Zeilen.

## Umsetzung

1. Repository: FK-Verletzung genau auf `agent_access_log_agent_id_fkey`
   in eine Domain-Exception `AccessLogRetainedError` uebersetzen; jede andere
   FK-Verletzung wandert unveraendert weiter (kein Verschlucken).
2. Service: `AccessLogRetainedError` -> `ApiError` 409, reason
   `concurrent_conflict` (dieselbe Wahl wie beim Agent-Delete, kein neues
   Vokabular), Detail mit Verweis auf Retention-/Purge-Pfad.
3. Router: 409-Beschreibung im OpenAPI-Schema um den zweiten Grund ergaenzen,
   `docs/reference/openapi.json` neu exportieren.
4. Tests: Integrationstest Workspace mit Log-Zeile -> 409, Log-Zeilen und
   Workspace unveraendert; Workspace ohne Log-Zeilen bleibt loeschbar.
   `known`-Eintrag in `test_tenant_isolation_api.py` entfernen.
5. Doku: `docs/compliance/agent-access-log.md` (Konsequenzen im Betrieb),
   Changelog-Fragment `fixed`.

## Verifikation

- `uv run pytest apps/api/tests/test_workspace_management.py
  apps/api/tests/test_tenant_isolation_api.py
  apps/api/tests/test_security_fixes_phase2.py` gegen eigene DB
- volle DoD laut CONTRIBUTING.md
