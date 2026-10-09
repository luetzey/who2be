- Worker: Die Zeitplan-Overrides aus ADR-0057 wirken jetzt im Betrieb. Jede
  Compose-Datei mit dem Dienst `worker` (lokal, Dokploy, Hetzner samt
  Overlays) reicht `WHO2BE_WORKER_ENABLED` und je Routine
  `WHO2BE_ROUTINE_<NAME>_SCHEDULE` und `WHO2BE_ROUTINE_<NAME>_ENABLED` an den
  Container durch. Bisher blieb ein Eintrag in der `.env` wirkungslos. Ohne
  Eintrag kommt ein leerer Wert an; er gilt als nicht gesetzt, es bleibt der
  Code-Zeitplan. Ein Drift-Test schlägt fehl, wenn eine registrierte Routine
  in einem Stack nicht durchgereicht wird.
