- Row Level Security deckt jetzt auch `workspace`, `organization` und
  `status_history` ab; die Policy von `mcp_usage` ist strikt (Migration 0092).

  Ist ein Mandant gesetzt, sieht die Laufzeitrolle `who2be_app` auch ohne
  `WHERE` der Anwendung nur den eigenen Workspace (samt den Geschwister-
  Workspaces der eigenen Organisation), die eigene Organisation, den eigenen
  Statusverlauf und die eigenen MCP-Zaehler. Ohne Mandanten (Login,
  Organisationsliste, Workspace anlegen) bleiben Workspaces und Organisationen
  fuer die Mandanten-Aufloesung lesbar, Statusverlauf und MCP-Zaehler nicht.

  `status_history` bekommt eine Spalte `workspace_id`. Sie wird aus der
  referenzierten Entity nachgetragen und beim Einfuegen per Trigger immer daraus
  abgeleitet; die Aufrufer bleiben unveraendert. Die Spalte haengt mit
  `ON DELETE CASCADE` am Workspace: der Purge einer Organisation oder eines
  Workspace entfernt jetzt auch deren Statusverlauf.
