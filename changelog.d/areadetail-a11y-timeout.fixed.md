- Der a11y-Test der Arbeitsbereichs-Detailseite läuft in der vollen Web-Suite
  nicht mehr ins 5-Sekunden-Timeout.

  Er prüfte alle drei Tabs mit je einem axe-Lauf in einem einzigen Test; unter
  CPU-Last summierte sich das auf über fünf Sekunden. Jetzt hat jeder Tab einen
  eigenen Test, das Timeout bleibt unverändert.
