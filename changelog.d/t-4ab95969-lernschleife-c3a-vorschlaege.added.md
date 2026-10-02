- Gedächtnis: Änderungs- und Löschvorschläge, Historie, Rückgängig,
  Bestätigen und Reaktivieren — Datenmodell und Service (ADR-0053,
  Paket C3a; die REST-Endpunkte folgen mit C3b).

  Ein Agent ändert oder löscht einen bestehenden Eintrag nie selbst: er
  schlägt es vor (Migration 0096, Tabelle `agent_memory_proposal`). Er kann
  nur zu Einträgen vorschlagen, die er auch abrufen darf (eigenes
  Agentengedächtnis, Nutzergedächtnis des Token-Besitzers, nur aktive
  Einträge), sonst `memory_not_found`. Der vorgeschlagene Text läuft durch
  Injection-Wächter und Secret-Scan wie `save_memory`; die Begründung ist
  Pflicht (höchstens 200 Zeichen). Ein Vorschlag wird nie automatisch
  angenommen, auch nicht unter `memory_mode=auto`. Ein Mensch entscheidet:
  Annahme einer Änderung schreibt `proposal_accepted` und `edited`, Annahme
  einer Löschung löscht den Eintrag hart mit inhaltsfreier
  `memory.deleted`-Spur. Ein bereits entschiedener Vorschlag antwortet mit
  `memory_proposal_not_pending` (409). Vorschläge zum Nutzergedächtnis sieht
  und entscheidet nur die Person selbst, auch `admin` nicht.

  Neu im Service: Historie eines Eintrags, Rückgängig auf den Stand vor einem
  Ereignis (`rolled_back`), Bestätigen (hebt den Verfall auf) und
  Reaktivieren abgelaufener Einträge. Ein unzulässiger Statuswechsel antwortet
  mit `memory_transition_invalid` (409). Bearbeiten durch einen Menschen
  schreibt jetzt das Ereignis `edited` mit Vorher-/Nachher-Stand. Die
  Historie kennt das Ereignis `auto_revoked` für den Not-Aus (6.4.1, C3b).
  Beim Löschen eines Kontos wird auch der Entscheider eines Vorschlags
  anonymisiert.
