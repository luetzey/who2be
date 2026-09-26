# ADR-0011 — Backup: GPG-verschluesselter Dump + restic auf Hetzner Storage Box

- Status: Akzeptiert
- Datum: 2026-05-26
- Kontext: Who2Be MVP (PROJ-19), MS-2 C5 / Plan-Review 2026-05-26

## Kontext

Der urspruengliche MS-2-C5-Plan sah `pg_dump` nach `/var/backups/who2be`
mit 7-Tage-Retention vor — alle Backups auf demselben Host wie die
Datenbank. Bei Host-Kompromittierung oder Hardware-Verlust gehen Daten
und Backups gemeinsam verloren. Fuer eine self-hosted AgentDB mit
versioniertem Prompt-Engineering ist das Risiko zu hoch.

## Optionen

- **A — Lokal-only (Status-quo-Plan).** Einfach, null Drittabhaengigkeit;
  kein Schutz gegen Host-Loss/Compromise. RPO 24h / RTO ≤30min nur,
  solange der Host lebt.
- **B — Lokal + Offsite (Hetzner Storage Box, restic, GPG).** Lokaler
  `pg_dump -Fc` wird mit GPG verschluesselt, `restic backup` synct
  inkrementell + deduplizert ins Hetzner-Storage-Box-Repo. Drittsystem
  ist im selben Hetzner-RZ → kein Egress-Cost. RPO 24h / RTO ≤2h.
- **C — Managed Postgres (Hetzner Managed DB / Supabase Cloud).**
  Backups, PITR und Patching outsourced. Bricht das "self-hosted"-
  Outcome des Projekts und kostet dauerhaft ≥ €30/Monat.

## Entscheidung

**B — GPG-encrypted Dump + restic auf Hetzner Storage Box.**

- `deploy/hetzner/scripts/backup.sh` macht
  `pg_dump -Fc | gpg --batch --yes -e -r <recipient>` → lokale Datei
  `/var/backups/who2be/dump-<ts>.pgc.gpg`, anschliessend
  `restic -r sftp:storagebox:/who2be backup /var/backups/who2be`.
- Retention: `restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6`.
- Cron taeglich 03:15 UTC im Compose-Stack (separater `backup`-Container
  oder Host-Cron, je nach Hetzner-Setup; Entscheidung in der konkreten
  C5b-Task).
- GPG-Public-Key wird per Secrets-File in den Container injiziert;
  Private-Key liegt **nicht** auf dem Host (Restore erfordert
  Operator-Key) — verhindert, dass ein kompromittierter Host die
  Backup-Inhalte entschluesseln kann.
- restic-Repo-Passphrase + Storage-Box-Credentials liegen im selben
  Secrets-File, eigene Sektion (`STORAGE_BOX_*`).
- `deploy/hetzner/scripts/restore.sh` macht den inversen Pfad gegen
  eine leere Test-DB; ist Vertrag fuer MS-3 H4 (produktiver Drill).

## Konsequenzen

- Neue Secrets-Eintraege: `STORAGE_BOX_HOST`, `STORAGE_BOX_USER`,
  `STORAGE_BOX_PASSWORD` (oder SSH-Key), `RESTIC_PASSWORD`,
  `BACKUP_GPG_RECIPIENT` (Key-ID).
- Operator muss den GPG-Private-Key sicher off-host verwahren — wird
  als RUNBOOK-Schritt dokumentiert.
- restic dedupliziert: 30 Tage Backups passen typischerweise in
  < 5 GB Storage-Box-Quota fuer eine kleine AgentDB.
- Restore-Drill (MS-3 H4) ist Pflicht — ohne dokumentierte
  Restore-Probe ist ein Backup ein Gefuehl, kein Wiederherstellungspfad.
- Secret-Rotation der Storage-Box-Credentials ist in MS-3 H8
  beschrieben (gemeinsame Rotation-Runbook).

## Nachtrag 2026-09-21 — Offsite-Fehlschlag ist nicht mehr still (Issue #541)

Die urspruengliche Fassung von `deploy/hetzner/scripts/backup.sh` behandelte
`restic backup` und `restic forget` bewusst als **nicht-fatal** und beendete den
Lauf auch bei gescheitertem Offsite-Sync mit Exit 0. Die Absicht war richtig: ein
gescheiterter Offsite-Sync darf den lokalen Dump nicht entwerten.

Die Nebenwirkung war es nicht. Ein Exit 0 macht den Cron-Lauf gruen; Storage Box
voll, SSH-Key abgelaufen oder Netzwerk weg blieben damit **monatelang unbemerkt**,
bis es beim Restore auffiel. Die Entscheidung stammt aus der Zeit vor einer
Betriebs-Alarmierung und wird hiermit vom Owner **ausdruecklich revidiert** — nicht
stillschweigend geloescht, sondern datiert ersetzt:

- **Exit != 0 bei gescheitertem `restic backup` oder `restic forget`.** Die Zusage
  "der lokale GPG-Dump bleibt erhalten" gilt **unveraendert** — der Dump ist an
  diesem Punkt bereits geschrieben und wird nicht angefasst. Weggefallen ist allein
  die falsche Erfolgsmeldung.
- **Zusaetzlich ein Dead-Man's-Switch** ueber `BACKUP_HEARTBEAT_URL` (leer = aus,
  Default): Ping nur bei vollstaendigem Erfolg, alarmiert wird durch das *Ausbleiben*
  des Pings. Das faengt zusaetzlich die Faelle, die ein Exit-Code prinzipiell nicht
  fangen kann (Cron aus, Container weg, Host aus).
- **Der Heartbeat-Empfaenger ist self-hosted.** healthchecks.io und jeder andere
  gehostete Dienst wurden vom Owner abgelehnt: ein Dritter waere Auftragsverarbeiter
  fuer Betriebsmetadaten und braeuchte einen VVT-Eintrag
  (`docs/compliance/vvt.md` §5). Mit einem selbst betriebenen Empfaenger entsteht
  kein solcher Eintrag.
- Belegt durch `deploy/hetzner/tests/test_backup_alarm.sh` (Stub-basiert, kein
  Docker-Daemon noetig); Einrichtung und Testanleitung im RUNBOOK unter
  "Backup & Restore" → "Alarmweg (Dead-Man's-Switch)". Die Suite laeuft im
  CI-Job `backup-alarm` (an `all-green` gebunden, `BACKUP_ALARM_REQUIRE_ALL=1`:
  ein uebersprungener Fall ist ein Fehlschlag).

Nicht Teil dieser Revision und weiterhin offen: RPO-Senkung / WAL-Archivierung, die
ungetesteten SeaweedFS-Blob-Kommandos (#532), der Restore-Drill (MS-3 H4 / #454).

## Nachtrag 2026-09-25 — Der Backup-Lauf umfasst alle drei Datenbestaende (W8/M3)

Diese ADR und `backup.sh` kannten bis hierher nur Postgres. Seit ADR-0048
(Objekt-Store) und ADR-0049 (Tabellen-Store je WorkArea) liegen zwei weitere
Nutzdaten-Bestaende ausserhalb der Datenbank: Postgres fuehrt von beiden nur den
Katalog (`wa_blob`, `wa_table`). Ein `pg_dump`-Restore allein ergibt damit eine
DB, deren Blob-Referenzen ins Leere zeigen, und leere Agenten-Tabellen.

Beschrieben war das im RUNBOOK laengst — als **Handarbeit**. Zwischen Doku und
Automatisierung klaffte eine Luecke, die im Ernstfall zwei Drittel der Nutzdaten
gekostet haette. Sie wird geschlossen:

- **`backup.sh` sichert drei Bestaende**, alle nach `${BACKUP_DIR}` und damit in
  **einen** restic-Snapshot: `pg_dump | gpg`, `aws s3 sync --delete` des
  Objekt-Store-Buckets, `VACUUM INTO`-Snapshots aller Area-SQLites.
- **Teilerfolg ist kein Erfolg.** Scheitert eine Stufe, endet der Lauf mit
  Exit != 0 und der Dead-Man's-Switch aus dem Nachtrag 2026-09-21 bleibt stumm.
  Ein gruener Lauf ist die Zusage „dieser Snapshot traegt den vollstaendigen
  Zustand"; ein halb gesichertes Backup darf sie nicht abgeben. Die Stufen
  brechen dabei nicht beim ersten Fehler ab — der Operator soll alle Baustellen
  eines Laufs kennen.
- **Unvollstaendige Snapshots sind als solche markiert:** `--tag incomplete`
  statt `--tag dump`. Die Daten gehen trotzdem offsite (ein Ausfall des
  Objekt-Stores soll den Dump nicht am Boden halten), koennen sich beim Restore
  aber nicht als vollstaendiger Stand ausgeben; die RUNBOOK-Restore-Pfade
  filtern auf `--tag dump`.
- **Fehlende Store-Konfiguration ist FATAL**, nicht „still uebersprungen" —
  stilles Ueberspringen ist genau der Fehlermodus, den dieser Nachtrag behebt.
  Abwahl nur ausdruecklich per `BACKUP_BLOBS=off` / `BACKUP_TABLESTORE=off`
  (On-Prem-Installationen ohne den jeweiligen Store).
- **Konsistenz-Grenze des Tabellen-Store-Snapshots:** `VACUUM INTO` liefert
  einen in sich konsistenten SQLite-Stand, haelt aber nicht den prozesslokalen
  Area-Write-Lock der API — ein fachlicher Vorgang ueber mehrere Transaktionen
  kann mittendrin erwischt werden (technisch intakte Datei, fachlich halber
  Import). Dokumentiert im RUNBOOK unter „Tabellen-Store-Backup".
- **Der Lauf darf den Schreibpfad der API nicht beruehren.** Eine WAL-Datenbank
  legt ihre Seitendateien (`-wal`, `-shm`) beim Oeffnen an — auch bei einem
  reinen Leser, und nachts ist genau das der Regelfall, weil die API je Query
  oeffnet und schliesst. Entstuenden sie unter der Kennung des Backup-Laufs,
  koennte die API die betroffene Area anschliessend nur noch lesen, nicht mehr
  schreiben: ein stiller Fehlermodus, der erst beim naechsten Tabellen-Schreiben
  auffiele. Deshalb laeuft der Lesevorgang je Datei unter der Kennung ihres
  Eigentuemers (`su-exec`) — und das Ergebnis wird **gemessen**, nicht
  angenommen: eine Seitendatei mit fremder Kennung macht die Area zum
  Fehlschlag. Bewusst nicht gewaehlt: sich darauf zu verlassen, dass SQLite die
  Kennung selbst nachzieht (das gelingt nur mit `CAP_CHOWN` und faellt still um,
  wenn die Capability entzogen wird), und die Seitendateien nachtraeglich zu
  loeschen (ein paralleler Leser der API koennte den WAL-Index gemappt haben).
- Der Tabellen-Snapshot entsteht in einem Vorlauf **im Zielverzeichnis** und
  wird erst nach bestandener Pruefung per `rename(2)` an seinen Platz geschoben;
  der Rueckgabewert wird ausgewertet. Auf demselben Dateisystem ist der
  Austausch unteilbar — ueber eine Grenze hinweg (Container-Writable-Layer vs.
  Backups-Volume) waere er ein Kopiervorgang, der an vollem Platz scheitern oder
  abgebrochen werden kann und das Ziel dabei ueberschreibt. Der letzte gute
  Snapshot ist genau der Stand, auf den ein Restore zurueckfaellt; er darf durch
  einen gescheiterten Lauf weder beschaedigt noch als Erfolg gezaehlt werden.
- Belegt durch `deploy/hetzner/tests/test_backup_alarm.sh` (14 Faelle,
  stub-basiert, kein Docker-Daemon noetig) — insbesondere Fall 7–9:
  Teilerfolg ⇒ Exit != 0, kein Heartbeat, `--tag incomplete`; Fall 12–13:
  Backup-Lauf und Store unter verschiedenen Kennungen, mit und ohne
  `CAP_CHOWN`; Fall 14: volllaufendes Backup-Ziel auf einem eigenen
  Dateisystem ⇒ Lauf rot, kein Heartbeat, Vortags-Snapshot unversehrt.

Weiterhin offen: der Restore-Drill (M2 / #454) — er ist der Beleg, dass die drei
Bestaende zusammen auch wirklich zurueckkommen.

</content>
</invoke>