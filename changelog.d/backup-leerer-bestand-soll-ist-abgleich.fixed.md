- Ein leerer Datenbestand gilt im naechtlichen Backup nicht mehr als Erfolg.

  `deploy/hetzner/scripts/backup.sh` erkannte bisher nur ein **fehlendes**
  Store-Verzeichnis, nicht ein vorhandenes und **leeres** — und
  `aws s3 sync --delete` gegen ein leeres oder falsches Bucket meldet Exit 0. Ein
  Volume-Mount, der nicht griff, ein umbenanntes Bucket oder ein verschobener
  `WHO2BE_TABLESTORE_DIR` sahen damit aus wie „nichts zu sichern": der Lauf endete
  gruen, pingte den Dead-Man's-Switch (#541) und trug `--tag dump`. Der
  Verwaisten-Sweep raeumte dabei sogar den letzten guten lokalen Spiegel.

  Jede Stufe haelt ihren Ist-Stand jetzt gegen den Postgres-Katalog in derselben
  Datenbank, die ohnehin gedumpt wird: `wa_table` nennt die erwarteten
  Area-Dateien (`{workspace_id}/{area_id}.sqlite`, ADR-0049), `wa_blob` die
  erwartete Objektzahl. Fehlt etwas, ist der Lauf rot, der Heartbeat bleibt aus
  und der Snapshot traegt `--tag incomplete`. Der legitime Leerfall — leerer
  Katalog, leerer Store auf einem frischen Stack — bleibt gruen; ein **nicht
  befragbarer** Katalog ist dagegen ein Fehlschlag und kein stilles „Soll 0"
  (das gilt auch, wenn `psql` mit Exit 0 antwortet, aber leer).

  Zwei Raeumvorgaenge setzen bei einer roten Stufe aus, weil sie sonst genau im
  scheiternden Lauf den Stand loeschen, auf den ein Restore zurueckfallen will:
  der Verwaisten-Sweep des Tabellen-Spiegels und `s3 sync --delete` (das
  Bucket-Inventar wird deshalb **vor** dem Sync gezaehlt). Reste eines hart
  abgebrochenen Vorlaufs (`.scratch.*`) fallen weiterhin in jedem Fall weg.

  Belegt durch `deploy/hetzner/tests/test_backup_alarm.sh` (jetzt 17 Faelle): die
  neuen Faelle 12–14 messen leeren Store bei nichtleerem Katalog (rot, 0 Pings,
  Spiegel unangetastet), den legitimen Leerfall (gruen) und ein leeres Bucket bei
  nichtleerem `wa_blob` (rot, ohne dass `s3 sync` lief). Gegen die Vorfassung sind
  12 und 14 rot — sie sind damit echter Regressionsschutz. RUNBOOK und ADR-0011
  nachgezogen.
