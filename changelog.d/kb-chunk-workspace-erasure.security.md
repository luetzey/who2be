- Wird ein Workspace gelöscht oder eine Organisation endgültig entfernt,
  verschwinden jetzt auch die Aussagen der Knowledge Base (`kb_node` samt
  Kanten, Belegen und Widersprüchen) und die Inhaltspassagen der Suche
  (`content_chunk`) dieses Workspace. Bisher blieben sie mit Inhaltstext und
  Autor (`created_by`) zurück. Migration 0105 löscht solche bereits verwaisten
  Zeilen einmalig und hängt die fünf Tabellen per `ON DELETE CASCADE` an den
  Workspace.
