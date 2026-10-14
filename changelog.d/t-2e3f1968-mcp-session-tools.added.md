- MCP-Werkzeuge für das Feedback-Gespräch (ADR-0053 6.6, Paket E-MCP-1):
  `get_dossier` (Vorbereitung, standardmäßig Markdown, `format="full"` als
  JSON), `submit_session_protocol` (Protokoll mit Fällen und Maßnahmen),
  `link_measure_draft` (Entwurf mit einer Maßnahme verknüpfen) und
  `get_follow_up` (Nachschau als Rohzahlen). Alle vier erscheinen nur mit
  `case_triage` in `tools/list`. Einstufen und Zurückziehen bleiben ohne
  Werkzeug. Damit hat der MCP-Server 94 Werkzeuge.
- Das Katalog-Budget für `tools/list` steigt von 160.000 auf 180.000 Bytes.
