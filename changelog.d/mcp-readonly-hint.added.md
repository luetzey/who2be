- MCP-Lesewerkzeuge tragen jetzt die Annotation `readOnlyHint: true` (42 von
  101 Werkzeugen). Clients wie ChatGPT fragen dann bei einem Lesezugriff nicht
  mehr jedes Mal nach. Schreibwerkzeuge bleiben ohne Annotation. Die
  Einordnung kommt aus `MCP_TOOL_REQUIREMENTS` (`ToolRequirement.is_read_only`),
  eine zweite Liste gibt es nicht. `get_follow_up` bleibt schreibend, weil
  beim Abruf ein Nachschau-Ereignis entstehen kann.
