- Wird ein Workspace gelöscht oder eine Organisation endgültig entfernt,
  verschwinden jetzt auch die Nutzungs- und Feedback-Meldungen der Agenten
  (`usage_event`, `agent_feedback` samt Triage) dieses Workspace. Bisher blieben
  sie mit Personenbezug (`actor_id`) und Feedback-Freitext zurück. Migration
  0104 löscht solche bereits verwaisten Zeilen einmalig und hängt beide
  Tabellen per `ON DELETE CASCADE` an den Workspace.
