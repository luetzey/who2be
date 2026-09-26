- Die Agents-Domäne ist auf Phone-Breiten bedienbar: technische Bezeichner
  (Persona- und Template-Namen, Token-Präfixe, gemerkte Fakten) bleiben in ihrer
  Spalte statt die Seite aufzuziehen, und die Zeilen-Aktionen der Listen erfüllen
  das 40-px-Hit-Target.

  Gemessen bei 320 px Viewport in Chromium gegen das gebaute Stylesheet: der
  horizontale Body-Scroll der geprüften Ansichten verschwindet (`scrollWidth`
  477 px → 320 px), die 21 Filter-Chips, Disclosure- und Zeilen-Buttons wachsen
  von 32 bzw. 36 px auf 40 px und fallen ab `md` auf die gewohnte Desktop-Dichte
  zurück. Die 40 px stammen aus dem Akzeptanzkriterium des Arbeitspakets; der
  verbindliche Floor der Design-Sprache liegt bei 32 px und war eingehalten.
  Das kombinierte Label der Token-Disclosure („1 abgelaufene · 2 widerrufene
  Tokens") bricht jetzt um, statt 44 px über den Kartenrand zu laufen.

  Zwei geprüfte Stellen bleiben absichtlich unverändert, weil die Messung dort
  keinen Defekt zeigt: die feste Breite des Wichtigkeits-Auswahlfelds (96 px in
  einer 204 px breiten Spalte) und die Zählerzeile der Token-Liste.
