- Werkzeug-Profile pro Agent, Datenhaltung (ADR-0059, Paket Q2a): Migration
  0111 legt die Tabelle `tool_profile` (je Workspace, RLS) und am Agenten die
  Spalten `tool_profile_id`, `tools_added` und `tools_removed` an. Jeder
  Workspace bekommt die vier mitgelieferten Profile Lesen, Autor, Kurator und
  Builder, benannt nach seiner Content-Sprache. Der verwaltete Builder und
  Builder-Lite stehen in neuen und bestehenden Workspaces auf dem Profil
  „Builder“ (Owner-Entscheidung W59-3). Alle anderen Agenten bleiben auf
  „Alle“. Die Agent-Antwort der API zeigt die drei Felder, und „Agent
  kopieren“ übernimmt sie von der Quelle. Ein Profil, das noch an Agenten
  hängt, lässt sich nicht löschen.

  Die Migrationsnummer ist 0111 statt der in der ADR genannten 0110, weil 0110
  inzwischen belegt ist. Noch ohne Wirkung auf `tools/list`: API-Endpunkte,
  `whoami` und MCP-Filter folgen in Q2b und Q3.
