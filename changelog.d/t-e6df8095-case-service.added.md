- Service-Schicht für Fälle (ADR-0053, Paket D2a): melden, lesen,
  Statuswechsel, Zuordnung zu Elementen, Schilderung des betroffenen Agenten
  und Löschen, mit den Rechten aus ADR-0053 Abschnitt 3.3. `viewer` sieht nur
  selbst gemeldete Fälle, `editor` und Agenten mit `case_triage` alle.
  Agent-Tokens setzen nie `addressed`, `verified`, `dismissed` oder
  `reopened`. `in_progress` und `verified` brauchen eine Maßnahme und werden
  bis Phase E abgewiesen. Neue Fehlergründe `case_not_found`,
  `case_transition_forbidden`, `case_transition_human_only` und
  `case_statement_not_subject`. HTTP-Routen folgen mit D2b.
