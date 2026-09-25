# W8/M3 — Backup sichert alle drei Bestaende (Blobs + Tabellen-Store in `backup.sh`)

Karte: `t_efdeef07` · Vorgaenger: `t_87ed8580` (PR #641, RUNBOOK) · Basis: `origin/main` @ `02dca8ad`

## 1 — Befund, selbst nachgemessen

```
$ grep -niE 'blob|tablestore|seaweed|sqlite|aws|s3|vacuum' deploy/hetzner/scripts/backup.sh
KEINE TREFFER
```

`backup.sh` (176 Zeilen auf `origin/main`) tut genau:

| Zeile | Schritt |
|---|---|
| `:91-95` | `pg_dump -Fc \| gpg --encrypt` → `${BACKUP_DIR}/dump-<ts>.pgc.gpg` |
| `:103-104` | lokale Retention: `dump-*.pgc.gpg` aelter als 7 Tage loeschen |
| `:156-162` | `restic backup ${BACKUP_DIR} --tag dump` |
| `:164-170` | `restic forget --keep-daily 7 … --prune` |
| `:174` | `heartbeat_or_fail` — **nur hier**, als letzte Aktion |

Der Compose-Service `backup` (`deploy/hetzner/who2be/docker-compose.yml:294-316`) haengt
nur an `supabase-net` und mountet nur `backups:` + die beiden Secret-Verzeichnisse.
`seaweedfs` liegt auf `app-net`, der Tabellen-Store im Volume `tablestore-data`.
**Der Backup-Container kann beide Bestaende heute technisch gar nicht erreichen** —
die Luecke ist nicht nur im Skript, sondern auch in Netz und Mounts.

RUNBOOK-Belege bestaetigt: `:982-983` (Blob-Referenzen zeigen ins Leere),
`:1090-1091` (`pg_dump`-Restore liefert leere Tabellen). Die Loesungsbloecke stehen
als Handarbeit in `:1028-1037` (`aws s3 sync`) und `:1098-1122` (`VACUUM INTO`).

## 2 — Entscheidungen (die Karte delegiert sie ausdruecklich)

### D1 — Wie kommt der Tabellen-Store-Snapshot zustande?

Der RUNBOOK-Block laeuft via `docker compose exec api python …` und nutzt
`TableStore.snapshot_to`, also den **prozesslokalen Area-Write-Lock** der API.
Aus dem Backup-Container heraus ist dieser Weg nicht verfuegbar.

| | Weg | Gegen |
|---|---|---|
| A | Docker-Socket in den Backup-Container mounten, `docker exec api …` | `/var/run/docker.sock` ist root-aequivalent auf dem Host — ein Backup-Container mit Host-Root-Aequivalenz ist ein schlechterer Tausch als die Konsistenz-Nuance, die er kauft |
| B | **`tablestore-data` in den Backup-Container mounten, `sqlite3 <src> "VACUUM INTO <dst>"`** | kein API-interner Lock — dafuer kein neues Privileg, kein neuer Netzpfad |
| C | Snapshot-Erzeugung in die API verlagern (Endpoint/CLI), Backup ruft sie | eigener Dienst-Vertrag, groesserer Umbau, gehoert nicht in diese Karte |

**Gewaehlt: B.** Begruendung und die Konsistenz-Grenze stehen unter D3.

### D2 — Darf ein Teilerfolg als Erfolg gelten? **Nein.**

Ein „gruener" Lauf ist eine Zusage an den Restore: *dieser Snapshot traegt den
vollstaendigen Zustand*. Ist ein Drittel nicht drin, ist die Zusage falsch — und
zwar genau dann falsch, wenn sie gebraucht wird. Der Dead-Man's-Switch (#541)
existiert, weil ein stiller Fehlschlag monatelang unentdeckt blieb; ein
Teilerfolg, der gruen meldet, ist derselbe Fehler mit anderem Anstrich.

Konkret:

1. Jede der drei Stufen, die scheitert, setzt `exit != 0`. `heartbeat_or_fail`
   steht unveraendert als **letzte** Aktion — damit ist „kein voller Erfolg ⇒
   kein Ping" strukturell, nicht durch Disziplin, garantiert.
2. **Der restic-Lauf faellt trotzdem**, aber der Snapshot wird
   `--tag incomplete` statt `--tag dump` getragen. Grund: die Zusage aus
   ADR-0011 („der lokale Dump bleibt erhalten und geht offsite") soll nicht an
   einem SeaweedFS-Ausfall sterben — aber ein unvollstaendiger Snapshot darf
   sich im Repo nicht als vollstaendiger ausgeben. Die Restore-Anleitung filtert
   deshalb ab jetzt `--tag dump`; ein `incomplete`-Snapshot wird von
   `restore latest --tag dump` nicht gezogen.
3. Fehler werden **gesammelt**, nicht beim ersten abgebrochen: scheitert der
   Blob-Sync, ist der Tabellen-Snapshot trotzdem einen Versuch wert. Der
   Operator soll nach einem Lauf alle Baustellen kennen, nicht nur die erste.

### D3 — `VACUUM INTO` auf einer laufenden SQLite: konsistent?

**Auf SQLite-Ebene ja, auf Anwendungsebene mit einer benannten Grenze.**

- `VACUUM INTO` laeuft als **Leser** in einer Transaktion. SQLite garantiert
  damit einen in sich konsistenten Punkt-in-der-Zeit-Stand; ein gleichzeitig
  schreibender Prozess kann den Snapshot nicht halb-geschrieben sehen. Die
  Zieldatei ist eigenstaendig lesbar, WAL-/SHM-Seitendateien werden nicht
  gebraucht.
- **Grenze:** der API-interne Area-Write-Lock (`TableStore.snapshot_to`) wirkt
  nur prozesslokal. Der Backup-Container haelt ihn nicht. Ein **fachlicher**
  Vorgang, der ueber mehrere SQLite-Transaktionen laeuft (z. B. ein Tabellen-
  Import in Bloecken), kann deshalb mittendrin erwischt werden: das Ergebnis ist
  eine technisch intakte Datei mit einem fachlich halben Import — nie eine
  korrupte Datei. Das ist dieselbe Eigenschaft, die `pg_dump` ohne
  `--serializable-deferrable` gegenueber laufenden Mehr-Schritt-Vorgaengen hat.
- Der naechtliche Lauf um 03:15 UTC trifft diesen Fall praktisch selten; er wird
  im RUNBOOK benannt statt weggelassen.
- Belegt wird jeder Snapshot mit `PRAGMA quick_check` (nicht `integrity_check`:
  gleiche Aussagekraft fuer Strukturfehler bei deutlich kuerzerer Laufzeit).

### D4 — Polaritaet der Schalter: Schweigen heisst nicht „uebersprungen"

Fehlende Env darf **nicht** stillschweigend zum Ueberspringen fuehren — das waere
exakt der Fehler, den diese Karte behebt. Beide neuen Stufen sind daher
**standardmaessig Pflicht** und nur per **ausdruecklichem** `BACKUP_BLOBS=off` /
`BACKUP_TABLESTORE=off` abwaehlbar (On-Prem-Installationen ohne SeaweedFS bzw.
ohne Tabellen-Store). Fehlt die Konfiguration ohne diese Abwahl → FATAL, wie beim
fehlenden `curl` in `:58-62`.

### D5 — Platz und Laufzeit

- `aws s3 sync` ist **inkrementell** (Vergleich ueber Groesse + Zeitstempel);
  uebertragen wird nur die Differenz zum Vorlauf.
- **Der lokale Spiegel waechst nicht mit der Retention.** Die 7-Tage-Retention in
  `:103-104` betrifft ausschliesslich `dump-*.pgc.gpg`. Blob-Spiegel und
  Tabellen-Snapshots sind **je genau eine** Kopie, die in place ueberschrieben
  wird. Lokaler Bedarf also `7 × Dump + 1 × Bucket + 1 × Tabellen-Store`, nicht
  `7 ×` davon. Die Historie traegt restic (dedupliziert).
- `--delete` im Blob-Sync und ein Abgleich-Schritt fuer verwaiste
  Tabellen-Snapshots verhindern, dass geloeschte Objekte/Areas lokal ewig
  weiterliegen (DSGVO-Loeschkonzept §4, „Restore-only-Re-Deletion").
- Das Skript loggt nach jeder Stufe die Groesse — damit ist Plattenwachstum im
  Cron-Log ablesbar, statt erst beim vollen Volume aufzufallen.

## 3 — Aenderungen

| Datei | Was |
|---|---|
| `deploy/hetzner/scripts/backup.sh` | Stufe 2 (Blob-Sync) + Stufe 3 (Tabellen-Snapshots) vor dem restic-Lauf; Fehler-Sammler; `--tag incomplete` bei Teilerfolg |
| `deploy/hetzner/backup/Dockerfile` | `aws-cli` + `sqlite` |
| `deploy/hetzner/who2be/docker-compose.yml` | `backup` bekommt `app-net`, `tablestore-data`-Mount und die SeaweedFS-Env |
| `deploy/hetzner/.env.example` | `BACKUP_BLOBS` / `BACKUP_TABLESTORE` dokumentiert |
| `deploy/hetzner/tests/test_backup_alarm.sh` | neue Faelle: Blob-Sync-Fehlschlag, Snapshot-Fehlschlag, beide → Exit != 0, **kein Ping**, Dump bleibt, `incomplete`-Tag |
| `deploy/hetzner/RUNBOOK.md` | beide Bloecke von „Handarbeit" auf „automatisiert" umgeschrieben; Restore auf `--tag dump`; Konsistenz-Grenze aus D3 |
| `docs/adr/0011-backup-gpg-restic-offsite.md` | datierter Nachtrag (Scope C5a: drei Bestaende) |
| `changelog.d/w8m3-backup-drei-bestaende.fixed.md` | Fragment |

## 4 — Verifikation (und ihre Grenzen)

Auf dieser Maschine **kein Docker-Daemon** — ein echter Lauf ist ausgeschlossen.
Ausgefuehrt wird:

```bash
bash -n deploy/hetzner/scripts/backup.sh
shellcheck deploy/hetzner/scripts/backup.sh deploy/hetzner/tests/test_backup_alarm.sh
bash deploy/hetzner/tests/test_backup_alarm.sh
docker compose -f deploy/hetzner/who2be/docker-compose.yml config   # nur wenn CLI ohne Daemon parst
uv run python scripts/changelog_fragments.py check
```

**Nicht** verifiziert und auch nicht behauptet: dass `aws-cli`/`sqlite` im
gebauten Alpine-Image tatsaechlich vorhanden sind (Paketexistenz in `v3.24`
wurde gegen den Alpine-Paketindex geprueft, der Build nicht), dass der
Backup-Container SeaweedFS ueber `app-net` erreicht, und dass ein echter
`VACUUM INTO` gegen eine von der API beschriebene Datei durchlaeuft. Das
gehoert in den Prod-Smoke (#454) bzw. den Restore-Drill (M2, Owner-Arbeit).

## 5 — Schritte

1. [ ] Befund verifizieren — **erledigt** (§1)
2. [ ] `backup.sh` umbauen
3. [ ] Dockerfile + Compose + `.env.example`
4. [ ] Tests erweitern, gruen fahren
5. [ ] RUNBOOK + ADR-Nachtrag, „manuell"-Stellen erschoepfend suchen
6. [ ] Changelog-Fragment
7. [ ] DoD-Kommandos, PR gegen `main`
