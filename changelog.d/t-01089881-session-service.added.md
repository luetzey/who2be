- Service-Schicht für Gesprächsprotokolle (ADR-0053, Paket E2b-1): ein
  Protokoll samt Fällen und Maßnahmen in einer Transaktion einreichen sowie
  Protokolle je ID und je Agent lesen. Einreichen und Lesen dürfen Menschen ab
  `editor` und Agenten mit `case_triage`. Fälle einer Maßnahme gehen in
  derselben Transaktion automatisch auf `in_progress` (aus `triaged`; aus
  `open` und `reopened` über `triaged`, wenn eine Zuordnung besteht). Fälle in
  anderem Status bleiben unverändert und werden im Ergebnis genannt. Neue
  Fehlergründe `session_cases_invalid`, `measure_test_case_required`,
  `measure_not_found` und `session_not_found`. HTTP-Routen folgen in einem
  eigenen Paket.
