- Einstellungen → Workspace → Gedaechtnis: Die Auto-Freigabe zeigt die
  Kennzahl „Letzte 7 Tage: n automatisch freigegeben · m davon bestaetigt“
  als Link auf die unbestaetigten Eintraege. Gezaehlt wird ueber
  `GET /memories/counts` mit `auto=true`; per Not-Aus zurueckgenommene
  Eintraege zaehlen nicht als bestaetigt.
