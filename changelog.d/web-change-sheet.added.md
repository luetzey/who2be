- Web: Im Review-Ergebnis öffnet „Änderung öffnen“ jetzt ein Sheet mit der
  Änderung (`?change=<id>`, ADR-0053 Phase E, Paket E5d). Es zeigt nur lesend
  die Felder (kleinste Änderung, Ziel, Prüffall, Erfolgskriterium,
  Gegenposition, Nachkontrolle, Entwurf mit Versionsstand, Rückmeldungen), die
  Kennzahlen der Nachkontrolle und den Verlauf. Die Kennzahlen stellen vorher
  (vN) und nachher (vM) gegenüber: bestandene Prüffall-Läufe, Rückmeldungen je
  100 Nutzungen (eine Nachkommastelle) und wieder aufgetretene Rückmeldungen.
  Die Richtung steht als Wort da. Bei zu wenig Nutzung erscheint ein Hinweis
  statt einer Richtung, vom Client gemeldete Läufe tragen „laut Client“. Die
  Kennzahlen werden erst ab „Aktiviert“ geladen. Ab `md` öffnet das Sheet
  rechts, darunter als Bottom-Sheet; dort stehen die Kennzahlen als Karten.
  `?change=first-due` öffnet die erste fällige Änderung. Eine unbekannte
  Änderung schließt das Sheet und meldet „Diese Änderung gibt es nicht
  (mehr).“ Zustand und Fälligkeit folgen dem Zustand vom Server.
