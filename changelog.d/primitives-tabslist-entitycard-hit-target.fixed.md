- Drei geteilte Primitive sind bei 320px bedienbar: die Tab-Leiste laesst sich
  scrollen statt Trigger unerreichbar zu klemmen, Karten-Titel brechen um, und
  Checkbox wie Radio erreichen den 32px-Hit-Floor. Weil es Primitive sind,
  wirkt jede der drei Korrekturen auf allen Seiten, die sie verwenden.

  `TabsList` rendert `whitespace-nowrap`-Trigger ohne Umbruch und ohne
  Scroll-Moeglichkeit. Die drei Tabs des Agenten-Editors summieren gemessen
  461px; bei 320px klemmte der Container auf 288px ab und der dritte Tab lag
  173px ausserhalb der Innenkante — per Hit-Test nicht erreichbar, auf keinem
  Weg. Die Detailseiten fuer Resources (4 Tabs, 540px) und Personae (498px)
  sind zusaetzlich bei 375px betroffen. `overflow-x-auto` macht die Leiste
  scrollbar; gegen eine umbrechende Leiste entschieden, weil sie die
  durchgehende Unterkante verliert und den aktiven Unterstrich in die obere
  Zeile setzt (gemessen 141px Leistenhoehe statt 45px).

  Der Titel-Link der `EntityCard` war beim Umbruch-Durchgang uebersehen
  worden, obwohl Beschreibung und Detail-Ueberschrift derselben Komponente ihn
  bekamen. Ein snake_case-Agentenname misst 282,5px und lief bei 320px 116,5px
  ueber seine Spalte. Die naheliegende Korrektur waere hier wirkungslos
  geblieben: der Titel ist ein Flex-Item mit `min-width: auto`, und
  `break-word` senkt dessen min-content-Breite nicht — der Ueberlauf blieb
  gemessen exakt gleich. `wrap-anywhere` senkt sie mit. Zusaetzlich noetig war
  eine Mindestbreite der Textspalte: traegt die Karte Zeilen-Aktionen wie auf
  der Agenten-Liste, kollabierte die Spalte bei 320px auf 0px und der Titel
  waere nach jedem einzelnen Zeichen umgebrochen (Karte 1522px statt 208px
  hoch) — eine schlimmere Regression als der Ausgangsfehler.

  `Checkbox` und `RadioGroupItem` messen 16px und unterschritten den
  verbindlichen Floor (§11: ≥ 32px) um die Haelfte. Die sichtbare Box bleibt
  unveraendert 16px, nur die klickbare Flaeche waechst auf 32px. Das Radio
  loest das mit einem Pseudoelement am Control; bei der Checkbox geht das
  nicht, weil ein `<input>` ein replaced element ist und keine Pseudoelemente
  rendert — dort tragen jetzt die Huelle die Optik und das Feld selbst die
  transparente Flaeche darueber. Zeilenhoehen, Abstaende und alle
  Zustandsfarben bleiben gemessen identisch.
