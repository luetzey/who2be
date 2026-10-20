- ADR-0058 (Accepted) legt fest, dass Agenten Inhalte künftig in Markdown
  schreiben, auch bei Teiländerungen. Das gilt für Persona, System-Prompt,
  Playbook, Resource und die `usage_notes` des externen Tools. Die
  Owner-Entscheidungen vom 2026-10-16 („W1a“, „M1b“) und vom 2026-10-20
  („1D, 2B, 3A, 4 ja“) stehen im Wortlaut darin. BlockNote bleibt das
  Speicherformat in der Datenbank und im Web-Editor, es gibt keine Migration.

  Die ADR beschreibt den Markdown-Umfang, Fehler statt stillem Verlust bei
  nicht abbildbaren Blöcken, die Rundlauf-Garantie mit Golden- und
  erzeugten Tests, Teiländerungen per Überschriften-Anker und die
  gemessene Budgetwirkung. Entschieden sind: Pflicht-Anker nur an
  Überschriften, Schreibvorlage über `format="source"`, harter Schnitt der
  JSON-Eingabe mit P3 vor dem Cloud-Release und `usage_notes` in Markdown.
  Tabellen gehen als GFM-Tabelle an den Agenten und werden nur im
  Resource-Editor angeboten, Zellen tragen nur Inline-Markdown ohne Pills
  (Owner-Entscheidung Editor-W1 vom 2026-10-20, BlockNote bleibt).
  Der Paketschnitt umfasst P1 bis P4. Es ändert sich noch kein Verhalten.
