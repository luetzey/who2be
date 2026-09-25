- Die Playbook-Detailseite, die Filterleiste der Übersicht und die beiden
  Auswahldialoge sind auf Phone-Breiten bedienbar: lange Playbook-, Persona- und
  Resource-Namen brechen um statt die Seite aufzuziehen, die Status-Segmentleiste
  und die Sub-Playbook-Zeilen brechen um, und die verdichteten Zeilen-Aktionen
  erfüllen unterhalb `md` das 40-px-Hit-Target aus dem Akzeptanzkriterium des
  Audits.

  Gemessen bei 320 px Viewport gegen das gebaute Stylesheet: die Seite erzeugte
  vorher 437 px Dokumentbreite bei 320 px Fensterbreite und liegt jetzt auf 320 px
  — sechs Überläufer gegen die Eltern-Innenkante sind auf null. Die
  Status-Segmentleiste lief 100 px über, der Playbook-Titel 117 px, die vier
  Karten des Beziehungs-Rasters je 133 px, die Sub-Playbook-Zeile zog den Dialog
  auf. Die Embed-Modus- und Reihenfolge-Buttons wachsen von 24 px auf 40 px, die
  Filter-Chips von 28 px, die Segment-Buttons und der Suchfeld-Reset von 32 px.
  Ab `md` bleiben alle Maße wie zuvor.
