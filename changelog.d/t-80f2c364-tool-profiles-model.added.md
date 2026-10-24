- Werkzeug-Profile pro Agent, Grundlage (ADR-0059, Paket Q1): Das neue Modul
  `who2be_models.tool_profiles` ist die einzige Quelle für die zehn
  Werkzeuggruppen, die Kern-Werkzeuge (`ping`, `whoami`, `report_problem`),
  die vier mitgelieferten Profile Lesen, Autor, Kurator und Builder (Builder
  mit `workarea_read`, Owner-Entscheidung W59-4) und die Sichtbarkeits-Formel
  „Rechte UND (Kern ODER Profil)“. `whoami` kennt das optionale Feld
  `tool_profile`, `report_problem` die Kategorie `tool_request` (W59-6).

  Noch ohne Wirkung: Datenbank, API, MCP-Filter und Oberfläche folgen in den
  Paketen Q2a bis Q5b. Ohne Profil verhalten sich alle Agenten wie bisher.
