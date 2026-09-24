- Die Playbooks-Liste und die Playbook-Detailseite sind auf dem Phone wieder
  lesbar, und die Tab-Leiste erzeugt dort keinen horizontalen Seiten-Scroll
  mehr.

  Die Tab-Leiste der Detailseite maß mit den deutschen Labels 403px gegen
  288px Spalte und schob die Seite bei 320px Viewport um 84px zur Seite; die
  Tabs brechen jetzt um. In der Listenzeile belegte die rechte Spalte mit
  Status und Tags feste 193px, wodurch der Textspalte daneben 0px blieben und
  Name, Beschreibung und Sub-Playbook-Namen aus ihrer Box liefen — unterhalb
  `md` liegt die Meta-Spalte jetzt als eigene Zeile unter dem Text, ab `md`
  bleibt die bisherige zweispaltige Anordnung. Genauso bei den verknüpften
  Resource-Blöcken: der Resource-Name hatte neben Badge und Entfernen-Aktion
  nur 106px und läuft nun über die volle Breite. Composite-Rückverweise mit
  langen zusammengeschriebenen Namen (gemessen 398px) brechen um, statt die
  Seite zu verbreitern.

  Drei Zeilen-Aktionen messen unterhalb `md` jetzt 40px statt 32px, 38px bzw.
  36px, entsprechend dem Akzeptanzkriterium von Issue #573; ab `md` bleibt die
  bisherige Dichte erhalten.
