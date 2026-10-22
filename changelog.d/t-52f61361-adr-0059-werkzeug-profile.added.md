- ADR-0059 (Accepted) beschreibt Werkzeug-Profile pro Agent als zusätzlichen
  Filter zu ADR-0042. Ein Profil blendet MCP-Werkzeuge aus, die ein Agent für
  seine Arbeit nicht braucht, und erweitert nie seine Rechte. Mitgeliefert
  werden „Alle“ (Standard, Bestand bleibt unverändert), „Lesen“, „Autor“,
  „Kurator“ und „Builder“. Am Agenten lassen sich einzelne Werkzeuge
  zusätzlich freigeben oder sperren. Die Owner-Entscheidungen vom 2026-10-16
  („W2b“, „P2a, P3a“, „P1 ok“) und vom 2026-10-21 zu den Weichen W59-1 bis
  W59-6 („Alle wie empfohlen, aber W59-4 ja“) stehen im Wortlaut darin.

  Die ADR legt Datenmodell (Tabelle `tool_profile`, Migration 0110), die
  Werkzeuggruppen, `whoami` und Cache (TTL 60 s), API und Rechte (Profile
  pflegt admin, zuordnen nur Menschen), den Meldeweg für ein fehlendes
  Werkzeug (`report_problem`, Kategorie `tool_request`) und den Paketschnitt
  Q1 bis Q6 fest. Das Profil „Builder“ enthält auch das Lesen im
  Arbeitsbereich; der verwaltete Builder bekommt es in neuen und bestehenden
  Workspaces. Gemessen sinkt sein Start von 115.807 auf 101.727 Bytes
  (−12,2 %), ohne neues MCP-Werkzeug. Es ändert sich noch kein Verhalten.
