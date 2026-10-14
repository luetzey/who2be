- MCP-Werkzeuge für die Werkzeuglücken aus D7 (ADR-0053 Phase E, Paket
  E-MCP-2): `get_case` (ein Fall im Volltext mit Zuordnungen, Schilderungen
  und Verlauf), `triage_case` (setzt einen Fall nur auf `triaged`),
  `list_patterns` (Muster samt Schwelle und Zeitfenster), `create_test_case`
  (Prüffall aus einem Fall mit `origin_case_id`), `get_lesson` (Lernvorschlag
  eines Agenten im Wortlaut) und `convert_lesson_to_case` (Lernvorschlag wird
  ein Fall). Alle sechs erscheinen nur mit `case_triage` in `tools/list`.
  Damit hat der MCP-Server 100 Werkzeuge.
- `list_cases` blättert jetzt: neuer Parameter `cursor`, die Antwort trägt
  `next_cursor` (`format="full"`) bzw. eine Folgezeile mit dem Cursor
  (Markdown). `format="full"` liefert dafür `{items, next_cursor}` statt einer
  bloßen Liste.
