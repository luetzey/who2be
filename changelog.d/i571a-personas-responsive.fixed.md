- Die Persona-Domäne ist auf Phone-Breiten bedienbar: die Tab-Leiste der
  Detailseite bricht um statt die Seite aufzuziehen, die Modus-Kopfzeile im
  `PersonaModesEditor` und der Kopf der Playbooks-Karte brechen um, lange
  Modus- und Sub-Playbook-Namen laufen nicht mehr aus der Karte, und die
  Aktionen dieser drei Bereiche erfüllen das 40-px-Hit-Target aus dem
  Akzeptanzkriterium des Audits.

  Gemessen bei 320 px Viewport gegen das gebaute Stylesheet: die Detailseite
  erzeugte 477 px Dokumentbreite (der Tab „Versionen" lief 173 px über die
  Leiste), das Default-Badge der Modus-Kopfzeile lief 121 px über, der
  Bearbeiten-Button der Playbooks-Karte 104 px und der Modi-Info-Pill 118 px;
  dem Sub-Playbook-Namen blieben 81 px von 329 px Textbreite. Danach passt jede
  Route der Domäne ohne horizontalen Body-Scroll, und die sechs angehobenen
  Bedienflächen messen 40 statt 32–36 px. Ab `md` bleiben alle Maße wie zuvor.
