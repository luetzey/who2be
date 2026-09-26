- Das Billing-Panel kuerzt seine Label-Zeilen auf schmalen Viewports, statt sie
  ueberlaufen zu lassen.

  Die drei `justify-between`-Zeilen (MCP-Kontingent, Speicher, Kartentitel mit
  Status-Badge) hatten zwei Flex-Kinder ohne `min-w-0` — bei `min-width: auto`
  schrumpft keines unter seine Inhaltsbreite, die Zeile lief auf 320 px ueber.
  Jetzt kuerzt das Label (`min-w-0 truncate`) und der Wert bleibt vollstaendig
  (`shrink-0`). Responsive-Audit aus Issue #561 (W3 von #431).
