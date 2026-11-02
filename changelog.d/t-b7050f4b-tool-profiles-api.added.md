- Werkzeug-Profile pro Agent, API und `whoami` (ADR-0059, Paket Q2b): Unter
  `/v1/workspaces/{id}/tool-profiles` lassen sich die Profile lesen (jedes
  Mitglied, mit Zahl der zugeordneten Agenten), der Katalog der Gruppen und
  Kern-Werkzeuge abrufen sowie eigene Profile anlegen, ändern und löschen und
  mitgelieferte auf den Lieferstand zurücksetzen. Pflegen darf nur `admin`
  (Owner-Entscheidung W59-2). Am Agenten setzt `PUT
  /agents/{id}/tool-profile` Profil, zusätzlich freigegebene und gesperrte
  Werkzeuge. Das darf `editor`, aber nur ein Mensch (403 `human_only` für
  Agent-Tokens), und es geht auch beim verwalteten Builder. `whoami` liefert
  das Feld `tool_profile` mit Gruppen und Ausnahmen, aber ohne ausgerechnete
  Werkzeugliste.

  Neue Fehlergründe: `tool_profile_not_found`, `tool_profile_name_conflict`,
  `tool_profile_in_use`, `tool_profile_builtin`, `tool_profile_not_builtin`,
  `unknown_tool`, `unknown_tool_group`, `core_tool_not_removable` und
  `human_only`. Jede Änderung steht im Audit-Log (`tool_profile.*`,
  `agent.tool_profile_changed`). Noch ohne Wirkung auf `tools/list`, der
  MCP-Filter folgt in Q3.
