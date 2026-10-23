- Builder-Inhalte bekommen Längen-Richtwerte und eine Wohin-Regel (Builder
  schlank B1, `BUILDER_CONTENT_VERSION` 19 → 20). Die Agent-Bau-Konventionen
  haben einen neuen Abschnitt „Längen & Wohin“, DE und EN (Anker
  `res-conv-h-laengen`). Er enthält Richtwerte je Element mit Ziel und
  Warnschwelle für Persona-Profil, Modus, Zahl der Modi, Playbook-Body,
  Beschreibung und Trigger, Resource-Abschnitt und Startlast. Dazu kommen eine
  Tabelle, welcher Inhalt in Profil, Playbook, Resource oder Gedächtnis
  gehört, und vier Schreibregeln. Die Zahlen stehen nur an dieser Stelle. Das
  Persona-Playbook prüft die Länge beim Vorschlag und beim Update. Der
  Konsistenz-Check meldet Überlängen als Pflege-Fund und nicht als Verstoß.
  Gekürzt wird nur auf Wunsch des Nutzers. Bestands-Workspaces erhalten die
  Fassung über den Builder-Sync.
