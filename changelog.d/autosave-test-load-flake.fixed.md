- Web-Tests: Die Auto-Save-Tests von PlaybookDetailPage und PersonaDetailPage
  warten auf das geladene Name-Feld jetzt bis zu 5 s statt mit dem
  `waitFor`-Default von 1 s. Unter fremder CPU-Last riss dieser Warte-Schritt
  die 1 s (auch auf main reproduziert). Die Assertion selbst und das globale
  `asyncUtilTimeout` bleiben unverändert.
