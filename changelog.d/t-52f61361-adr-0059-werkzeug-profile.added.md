- ADR-0059 (Proposed) beschreibt Werkzeug-Profile pro Agent als zusätzlichen
  Filter zu ADR-0042. Ein Profil blendet MCP-Werkzeuge aus, die ein Agent für
  seine Arbeit nicht braucht, und erweitert nie seine Rechte. Mitgeliefert
  werden „Alle“ (Standard, Bestand bleibt unverändert), „Lesen“, „Autor“,
  „Kurator“ und „Builder“. Am Agenten lassen sich einzelne Werkzeuge
  zusätzlich freigeben oder sperren. Die Owner-Entscheidungen vom 2026-10-16
  („W2b“, „P2a, P3a“, „P1 ok“) stehen im Wortlaut darin.

  Die ADR legt Datenmodell (Tabelle `tool_profile`, Migration 0108), die
  Werkzeuggruppen, `whoami` und Cache, API und Rechte, den Meldeweg für ein
  fehlendes Werkzeug und den Paketschnitt Q1 bis Q6 fest. Gemessen sinkt der
  Start des Builders mit dem Profil „Builder“ von 115.807 auf 95.590 Bytes,
  ohne neues MCP-Werkzeug. Sechs Weichen sind mit Empfehlung offen. Es ändert
  sich noch kein Verhalten.
