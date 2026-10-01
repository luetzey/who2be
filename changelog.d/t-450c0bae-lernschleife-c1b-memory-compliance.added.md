- Das Gedächtnis 2.0 ist jetzt in Auskunft und Löschung eingebunden (ADR-0053,
  Paket C1b). Der DSGVO-Export enthält je Workspace das Nutzergedächtnis der
  exportierenden Person als `user_memories`; beide Gedächtnisblöcke tragen je
  Eintrag ihre Historie unter `events`. `agent_memories` enthält nur noch das
  Agentengedächtnis – Fakten über andere Mitglieder stehen nicht mehr im
  Export.

  Beim Löschen eines Kontos entfernt der Purge das Nutzergedächtnis der
  Person in allen Workspaces und hinterlässt je Eintrag eine Zeile
  `memory.deleted` im Audit-Log, ohne Inhalt. Wer Einträge bestätigt oder in
  der Historie als Mensch gehandelt hat, wird auf die anonyme Kennung
  gesetzt. VVT (V17) und Löschkonzept (§4c) nennen die neuen Kategorien und
  den Verfall unbestätigter Einträge nach 30 Tagen.
