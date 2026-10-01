- Die Playbook-Liste läuft bei 768 und 1024 px nicht mehr horizontal über.
  Ab `md` war die Tag-Spalte einer Zeile unbegrenzt breit: Mit 12 Tags wurde
  sie 1236 px breit, drückte die Textspalte mit Name und Beschreibung auf
  0 px, und die Seite scrollte seitlich (scrollWidth 1593 bei 768 px). Die
  Spalte hat jetzt einen Deckel, 10rem ab `md` und 20rem ab `lg`, und die Tags
  brechen darin um. Bei 12 Tags bleiben der Textspalte 210 px (768), 306 px
  (1024) und 546 px (1280). Zeilen mit wenigen Tags sehen aus wie vorher.
