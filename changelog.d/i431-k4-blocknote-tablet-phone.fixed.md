- Der BlockNote-Editor ist auf dem Tablet bedienbar und auf dem Phone lesbar (#431).

  Das Side-Menu (Drag-Handle und „+") wird unterhalb `md` ausgeblendet: der
  Rinnen-Override aus #564 nimmt dem Editor die 54px breite Spalte, in der
  BlockNote das Menü positioniert, und es lag danach bei `x = -21` zu einem
  Grossteil ausserhalb des Viewports. Basis-Editing bleibt vollstaendig
  erhalten (neuer Block per Enter, Blocktyp per Slash-Menü, Formatting-Toolbar)
  — per reinem Touch-Tap nachgewiesen.

  Toolbar-Buttons, Side-Menu-Buttons und die Eintraege des Drag-Handle-Menues
  liegen jetzt auf dem 32px-Floor aus `docs/frontend/design-language.md` §11;
  gemessen lagen sie bei 30x30, 24x24 bzw. 94x30. Der Blocktyp-Button der
  Toolbar schrumpfte bei 320px auf 18,7px Breite und haelt seine Mindestbreite
  jetzt, statt zu kollabieren.
