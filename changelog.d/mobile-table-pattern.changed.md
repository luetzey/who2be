- Breite Datentabellen sind auf dem Telefon besser bedienbar (Mobil-Spec
  M11), zuerst in der Arbeitsbereich-Tabelle.

  Läuft eine Tabelle über, ist ihr Scroll-Bereich per Tab erreichbar und nach
  der Kartenüberschrift benannt (etwa „Daten“), sodass die Pfeiltasten ihn
  scrollen. Die erste Spalte bleibt links stehen und bekommt beim Scrollen
  eine Schattenkante. Ein Verlauf am rechten Rand zeigt weitere Spalten an,
  und unter `md` steht darunter „Seitlich wischen für weitere Spalten“. Ein
  Wisch am Rand läuft nicht mehr in die Seite weiter. Passt die Tabelle, bleibt
  alles wie bisher: kein zusätzlicher Tab-Stopp, kein Hinweis. Vorher war der
  Bereich bei 320px (238 von 988px sichtbar) nicht fokussierbar, und die erste
  Spalte scrollte mit weg.

  `Table` hat die neue Prop `labelledBy` (id der sichtbaren Überschrift). Auch
  das Navigations-Menü auf dem Telefon lässt einen Wisch am Listenende nicht
  mehr in die Seite dahinter durch.
