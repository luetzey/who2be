- ADR-0058 (Proposed) legt fest, dass Agenten Inhalte künftig in Markdown
  schreiben, auch bei Teiländerungen. Das gilt für Persona, System-Prompt,
  Playbook und Resource. Die Owner-Entscheidung vom 2026-10-16 („W1a“, „M1b“)
  steht im Wortlaut darin. BlockNote bleibt das Speicherformat in der
  Datenbank und im Web-Editor, es gibt keine Migration.

  Die ADR beschreibt den Markdown-Umfang, Fehler statt stillem Verlust bei
  nicht abbildbaren Blöcken, die Rundlauf-Garantie mit Golden- und
  erzeugten Tests, Teiländerungen per Überschriften-Anker und die
  gemessene Budgetwirkung. Dazu kommen der Paketschnitt P1 bis P5 und vier
  Weichen für den Owner: Block-IDs, Schreibvorlage `format="source"`,
  Auslauf der JSON-Eingabe und `usage_notes`. Es ändert sich noch kein
  Verhalten.
