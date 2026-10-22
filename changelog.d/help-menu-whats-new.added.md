- „?“-Menü in der Kopfzeile links neben der Glocke (Onboarding P5): Erste
  Schritte mit Fortschritt (holt eine ausgeblendete Startliste zurück und setzt
  den Fokus darauf), Tutorials, Hilfe durchsuchen, Was ist neu, „Einführung
  erneut starten“ (setzt das Tutorial „Erste Schritte“ zurück, fragt nur nach,
  wenn dabei Fortschritt verloren geht) und Problem melden. Die Tutorials lädt
  das Menü erst beim Öffnen.
- Seite „Was ist neu“ unter `/w/:workspaceId/help/neu`, nach Monat gruppiert,
  dazu die letzten zwei Einträge auf der Hilfe-Startseite. Einträge sind
  Markdown-Dateien je Sprache unter `apps/web/src/help/news/` (Frontmatter
  `date`, `type`, `title`, optional `link`); der Inhaltstest prüft Schema,
  DE/EN-Parität und Links. Der Hinweis-Punkt am Menü kommt später.
