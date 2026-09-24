- jsdom auf 30.1.0 angehoben (von 29.1.1) und die dadurch ausgelösten
  13 Testfehler behoben.

  jsdom 30 hat die „focus fixup rule" umgestellt: entfernt man das fokussierte
  Element aus dem DOM — genau das tut `cleanup()` von Testing Library —, zeigt
  die interne Fokus-Buchhaltung nicht mehr auf `null`, sondern auf das
  Document. Der nächste `focus()`-Aufruf hielt das für „vorher war etwas
  fokussiert" und feuerte ein `blur`, das durch die Target-Adjustment-Regel am
  `window` landete. Radix' Menu-Root schließt auf genau dieses `window`-`blur`,
  weshalb sich jedes Dropdown ab dem **zweiten** Test einer Datei sofort nach
  dem Öffnen wieder schloss (Export-Menüs, WorkspaceSwitcher, Dropdown-Cap).
  Das globale Test-Setup stellt die Fokus-Buchhaltung nach jedem `cleanup()`
  wieder auf „nichts fokussiert" — ein Testumgebungs-Artefakt, kein
  Anwendungsfehler: die Export-Downloads sind in echtem Chromium gegen das
  gebaute Bundle gegengeprüft und funktionieren unverändert.
