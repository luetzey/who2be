- Der DSGVO-Export (`GET /v1/gdpr/export`) gibt das Agentengedaechtnis eines
  Workspace nur noch ab der Rolle `editor` heraus — dieselbe Grenze wie in der
  Oberflaeche. Ein `viewer` bekam es bisher ueber den Export, obwohl er es in der
  App nicht sehen darf. Sein Block `agent_memories` bleibt jetzt leer, und das
  neue Feld `export_manifest.agent_memories` (`included`, `reason`) erklaert
  warum.

  Die Gedaechtnis-Historie (`agent_memory_event`) wird nur noch fuer die
  exportierten Eintraege gelesen statt workspace-weit; Ereignisse zu
  Nutzerfakten anderer Mitglieder werden nicht mehr geladen.
