- Builder-Inhalte beschreiben den Markdown-Schreibweg nach ADR-0058 (W1-P4a,
  `BUILDER_CONTENT_VERSION` 18 → 19). Die verwalteten Playbooks für Persona,
  Playbook, Agent, externes Tool und Feedback-Gespräch sowie die
  Agent-Bau-Konventionen nennen jetzt, DE und EN: Vorlage mit
  `format="source"` lesen (Quell-Markdown mit Überschriften-Ankern und
  `base_rev`), Teiländerungen über `edit_content`, Vollstand über `update_*`
  in Markdown, Platzhalter als `{{kind:target_id}}`, `usage_notes` des
  externen Tools als Markdown. Editor-JSON als Schreibweg und `format="full"`
  als Vorlage sind entfallen. Bestands-Workspaces erhalten die Fassung über
  den Builder-Sync. Ausgeliefert wird das im selben Release wie die
  MCP-Umstellung (W1-P3), weil die Werkzeuge erst dann Markdown annehmen.
