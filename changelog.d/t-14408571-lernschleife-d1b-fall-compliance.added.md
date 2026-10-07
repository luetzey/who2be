- Fälle sind in Datenexport und Kontolöschung eingebunden (ADR-0053, Paket
  D1b). Der DSGVO-Export enthält je Workspace die Fälle samt Verlauf,
  Zuordnung und Schilderung. Ab der Rolle `editor` sind das alle Fälle des
  Workspace, darunter nur die selbst gemeldeten; `export_manifest.cases` sagt,
  welche Regel galt. Die Kontolöschung anonymisiert in fremden Workspaces die
  meldende Person, menschliche Akteure im Verlauf und menschliche Zuordnungen.
  Ein Fall lässt sich jetzt auch löschen, wenn ein Lernvorschlag in ihn
  umgewandelt wurde: der Lernvorschlag wird mitgelöscht, beide hinterlassen
  eine Audit-Zeile ohne Inhalt. VVT und Löschkonzept sind ergänzt.
