- Das Datenmodell für Gedächtnis 2.0 steht (ADR-0053, Paket C1a). Migration
  0091 erweitert `agent_memory` um Art (`user_fact`, `agent_note`, `lesson`),
  Geltungsbereich (`agent` oder `user`) und Herkunft. Dazu kommen
  Bestätigung, Verfallszeitpunkt, Wiederholungszähler und der Verweis auf
  einen Fall. Die Status `expired` und `converted` sind neu. Neu ist auch die
  append-only Historie `agent_memory_event`.

  Die Datenbank sichert die Regeln selbst ab: Ein Lernvorschlag kann nie
  `active` werden. Ein Nutzerfakt gehört genau einem Nutzer und keinem
  Agenten; er bleibt erhalten, wenn der einreichende Agent gelöscht wird.
  `converted` ist nur mit Fall-Verweis möglich. Bestehende Einträge gelten
  als Agentengedächtnis mit unbekannter Herkunft; aktive Einträge gelten als
  bestätigt. Wer einen Eintrag löscht, hinterlässt eine Zeile
  `memory.deleted` im Audit-Log, ohne Inhalt. Der Abruf liefert unverändert
  nur aktives Agentengedächtnis. Freigabematrix, Obergrenzen und MCP folgen
  in C2a bis C4.
