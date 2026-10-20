- Konverter zwischen BlockNote und Markdown in `who2be_models.blocknote_markdown`
  (ADR-0058, Paket P1): `to_markdown`, `from_markdown` mit Basisversion und
  Block-Zuordnung je Abschnitt, `normalize` fuer die Normalform. Was Markdown
  nicht abbilden kann, erscheint lesend als geschuetzter Marker und endet
  schreibend als `MarkdownConversionError` statt als stiller Verlust. Noch ohne
  Verhaltensaenderung: API und MCP nutzen den Konverter erst ab P2/P3.
