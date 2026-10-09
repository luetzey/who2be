- Betrieb: Purge und Gedächtnis-Verfall werden nicht mehr als Host-Cron bzw.
  Dokploy-Schedule eingeplant. Sie laufen als Routinen `purge` und
  `memory-expire` im Compose-Dienst `worker` (ADR-0057 §8). Das RUNBOOK
  beschreibt im neuen Abschnitt „Hintergrund-Routinen (Worker)“ Prüfung
  (`who2be-worker list`, Laufprotokoll `routine_run`), Overrides, manuellen
  Lauf, Notfallweg über die CLIs und das Entfernen alter Crontab-Zeilen.
  `docs/cloud-erstinbetriebnahme.md` sagt für Dokploy, dass bestehende
  Schedules gelöscht werden. Erstinbetriebnahme, Architektur-Überblick,
  Löschkonzept und `.env.example` sind entsprechend angepasst.
