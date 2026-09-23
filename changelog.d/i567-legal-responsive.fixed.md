- Die Rechtsseiten unter `/legal/*` erzeugen auf dem Phone keinen horizontalen
  Seiten-Scroll mehr, und die beiden Buttons des Cookie-Banners sind dort
  leichter zu treffen.

  Der Seitentitel war mit 30px so groß, dass die längsten deutschen Titel aus
  der Lesespalte liefen — gemessen bei 320px Viewport 337px Textbreite gegen
  288px Spalte auf der AGB-Seite; unter `sm` steht er jetzt eine Stufe kleiner.
  Langer Fließtext ohne Trennstellen (URLs, E-Mail-Adressen, Registerangaben)
  bricht am gemeinsamen Artikel-Rahmen um, statt überzulaufen. Die Buttons des
  Cookie-Banners messen unterhalb `md` 40px statt 36px und teilen sich unter
  `sm` die volle Kartenbreite.
