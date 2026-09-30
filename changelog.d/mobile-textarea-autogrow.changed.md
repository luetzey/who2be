- Mehrzeilige Textfelder wachsen mit dem Inhalt, statt innen zu scrollen
  (Mobil-Spec M5). Vorher hatte etwa die Agent-Beschreibung bei 320 px eine
  sichtbare Höhe von 78 px bei 1.276 px Inhalt, also 16-fach innen
  scrollbar; auf dem Telefon scrollte das Wischen über das Feld das Feld statt
  der Seite. Jetzt wächst jedes `Textarea` bis 60 % der kleinen
  Viewporthöhe (`max-h-[60svh]`); erst darüber scrollt es innen, damit die
  Tastatur Platz behält. `rows` bleibt die Mindesthöhe.

  Browser mit `field-sizing: content` brauchen dafür kein JavaScript. Für
  Safari vor 26.2 und Firefox vor 152 setzt der neue Hook `useAutoGrow` die
  Höhe beim Tippen; die Scrollposition der Seite und der Fokus bleiben dabei
  stehen. Token-Anzeige und MCP-Konfiguration behalten ihre feste Höhe
  (`autoGrow={false}`).
