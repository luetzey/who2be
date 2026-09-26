- Playwright faehrt die E2E-Suite jetzt auf vier Profilen statt einem:
  `chromium` (Desktop, unveraendert) sowie neu `mobile-iphone-13`,
  `tablet-ipad-gen-7` und `mobile-320` (eigener 320x568-Viewport als
  Layout-Untergrenze).

  Die drei neuen Profile laufen in einem eigenen CI-Job `e2e-mobile` (Matrix,
  ein Lauf je Profil) und sind bewusst **noch kein Gate**: der Job steht nicht
  in der `needs`-Liste des Aggregat-Jobs `all-green` und traegt zusaetzlich
  `continue-on-error: true`. Er meldet also, blockiert aber keinen Pull
  Request. Das Scharfstellen ist ein eigener, spaeterer Schritt.
