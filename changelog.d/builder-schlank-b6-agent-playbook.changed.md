- Das Agent-Playbook des Builders ist entschlackt (Builder schlank B6,
  `BUILDER_CONTENT_VERSION` 22 → 23, DE und EN). Die Abläufe (Create, Update,
  Copy, Deaktivieren) bleiben im Playbook. Das Nachschlagewissen steht jetzt
  in den Agent-Bau-Konventionen: Template-Schreibweg und Platzhalter im neuen
  Abschnitt „System-Prompt-Templates verfassen“ (`res-conv-h-templates`), den
  der Builder nur lädt, wenn er ein Template verfasst; die Policy- und
  Gedächtnis-Fakten in den Abschnitten `res-conv-h-policy` und
  `res-conv-h-memory`. Ein Agenten-Bau (Persona- und Agent-Playbook samt
  geladenen Abschnitten) lädt so auf Deutsch 22,7 KB statt 31,6 KB, auf
  Englisch 22,1 KB statt 30,5 KB. Bestands-Workspaces erhalten die Fassung
  über den Builder-Sync.
