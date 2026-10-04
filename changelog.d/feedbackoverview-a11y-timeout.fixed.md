- Der a11y-Test der Feedback-Übersicht läuft im Coverage-Lauf unter Last
  nicht mehr ins 15-Sekunden-Timeout.

  Er prüfte beide Tabs (Posteingang und Kuration) mit je einem axe-Lauf in
  einem einzigen Test; unter CPU-Last summierte sich das auf über 15 Sekunden.
  Jetzt hat jeder Tab einen eigenen Test, das Timeout bleibt unverändert.
