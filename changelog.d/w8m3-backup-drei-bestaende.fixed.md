- Das naechtliche Backup sichert jetzt alle drei Datenbestaende statt nur Postgres (W8/M3).

  `deploy/hetzner/scripts/backup.sh` spiegelt zusaetzlich den Objekt-Store
  (ADR-0048, `aws s3 sync --delete`, inkrementell) und erzeugt `VACUUM INTO`-
  Snapshots aller WorkArea-SQLites (ADR-0049) — beide nach `/var/backups/who2be`
  und damit in denselben restic-Snapshot wie der GPG-Dump. Postgres fuehrt von
  beiden nur den Katalog (`wa_blob`, `wa_table`); ein Restore aus dem bisherigen
  Backup haette eine DB mit toten Blob-Referenzen und leeren Tabellen ergeben.
  Die Schritte standen bisher nur als Handanleitung im RUNBOOK.

  Ein Teilerfolg gilt dabei nicht als Erfolg: scheitert eine der drei Stufen,
  endet der Lauf mit Exit != 0, der Dead-Man's-Switch (#541) bleibt stumm, und
  der restic-Snapshot traegt `--tag incomplete` statt `--tag dump` — er kann sich
  beim Restore also nicht als vollstaendiger Stand ausgeben. Fehlende
  Store-Konfiguration ist ein Fehler, kein stilles Ueberspringen; abwaehlbar nur
  ausdruecklich per `BACKUP_BLOBS=off` / `BACKUP_TABLESTORE=off`.

  Belegt durch `deploy/hetzner/tests/test_backup_alarm.sh` (11 Faelle,
  stub-basiert, ohne Docker-Daemon lauffaehig). RUNBOOK und ADR-0011 nachgezogen.
