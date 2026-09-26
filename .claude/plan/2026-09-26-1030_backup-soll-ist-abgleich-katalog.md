# Backup: leerer Bestand gilt als Erfolg — Soll-Ist-Abgleich gegen den Postgres-Katalog

Karte: `t_a6872d5f` (hinter `t_efdeef07` / PR #645, gemergt als Teil von `main`)
Basis: `a2bf65df` (origin/main)
Datei im Zentrum: `deploy/hetzner/scripts/backup.sh`

## 1. Befund — selbst reproduziert

Mit PATH-Stubs (pg_dump/gpg/restic/curl), `BACKUP_BLOBS=off`, zwei Läufen auf
dasselbe `BACKUP_DIR`:

    --- Lauf 1: echter Store
    EXIT=0 PINGS=1 --tag dump
       Snapshots im Ziel danach: 1
    --- Lauf 2: vorhandenes, LEERES WHO2BE_TABLESTORE_DIR
    EXIT=0 PINGS=1 --tag dump
       [backup]   · verwaisten Snapshot entfernt: aaaa/bbbb.sqlite
       [backup] Tabellen-Snapshots: 0 Datei(en), 0
       [backup] fertig ✓ (Postgres + Objekt-Store + Tabellen-Store)
       Snapshots im Ziel danach: 0

Deckt sich mit dem Kartenbefund. `:317` prüft `[[ ! -d ]]` — ein vorhandenes,
leeres Verzeichnis passiert die Prüfung, die `find`-Schleife läuft null Mal,
die Merkliste bleibt leer, und der Verwaisten-Sweep (`:435-441`) hält damit
**jeden** vorhandenen Snapshot für verwaist.

## 2. Design-Weiche: woher kommt die Soll-Zahl?

Entschieden: **Postgres-Katalog** (`wa_table`, `wa_blob`) über `psql` gegen
dieselbe Datenbank, die der Lauf ohnehin dumpt.

Belege für die Tragfähigkeit (im Repo nachgelesen, nicht angenommen):

- `wa_table` (Migration `0078_wa_table.sql:30`) trägt `workspace_id` + `area_id`;
  `TableStore.db_path` (`tablestore/engine.py:424`) baut den Dateipfad als
  `{base_dir}/{workspace_id}/{area_id}.sqlite` aus genau diesen beiden IDs.
  Der Katalog nennt damit nicht nur eine *Zahl*, sondern die **erwarteten
  Pfade**.
- `WaTableService.create` (`services/wa_tables.py:520`) legt Katalog-Zeile und
  SQLite-Tabelle in einer Postgres-Transaktion an und rollt die Zeile bei
  DDL-Fehler zurück. Invariante: **Katalog-Zeile ⇒ Datei existiert.** Die
  Umkehrung gilt nicht (`drop_table` löscht die Tabelle, nicht die Datei) —
  die Prüfung ist deshalb bewusst asymmetrisch: *jede im Katalog genannte Area
  muss eine Datei haben*, überzählige Dateien sind kein Fehler.
- `wa_blob` (`0075_wa_blob.sql:20`) trägt `storage_key` = `blobs/{ws}/{sha256}`.
  Für Blobs genügt der Zählvergleich „Ist ≥ Soll"; Orphan-Objekte im Bucket
  erhöhen Ist, senken es nie.
- `psql` liegt bereits im Image (`backup/Dockerfile:26`, `postgresql16-client`),
  Credentials und Netzwerkweg sind dieselben wie für `pg_dump`
  (`docker-compose.yml:385-388`). RLS greift nicht, weil der Lauf als
  `supabase_admin` verbindet — dieselbe Kennung, die den Dump zieht.

**Keine Folgekosten außerhalb des Skripts:** keine neue Abhängigkeit, kein
neues Secret, kein neuer Netzwerkweg, kein neuer Dienst (also kein
Auftragsverarbeiter und kein VVT-Eintrag), kein Deploy-Schritt, kein neuer
Env-Schalter. Damit ist das keine Frage für @pm, sondern eine belegte
Entscheidung.

### Verworfene Alternativen

| Option | Warum nicht |
|---|---|
| **Marker-Datei im Volume** | Erkennt den nicht gegriffenen Mount, sagt aber nichts über den **Inhalt**: ein Volume, das die Marker-Datei trägt und dessen Areas verschwunden sind, gilt weiter als gesund. Braucht außerdem einen Deploy-Schritt, der sie anlegt und pflegt — genau die Folgekosten außerhalb des Skripts, die die Karte ausschließt. |
| **Mindestanzahl per Env** (`BACKUP_TABLESTORE_MIN_AREAS`) | Driftet mit jeder neuen Area und muss von Hand nachgezogen werden. Ein zu niedrig gesetzter Wert macht die Prüfung wirkungslos, ohne dass es auffällt — eine Zusage, die an Disziplin hängt, ist die Klasse Fehler, die #541 geschlossen hat. |
| **Katalog** (gewählt) | Wächst und schrumpft synchron mit dem Bestand, ohne eigene Pflege. Einzige Quelle, die „leer, weil nichts da" von „leer, weil der Mount nicht griff" **unterscheiden kann**. |

Der legitime Leerfall bleibt damit grün: leerer Katalog ⇒ Soll 0 ⇒ leerer
Store ist erwartungskonform. Fehlt die Katalog-Tabelle ganz (frischer Stack
vor Migration 0078), gilt ebenfalls Soll 0 — geprüft über `to_regclass`, nicht
über einen unterdrückten Fehler.

## 3. Änderungen an `backup.sh`

1. **`catalog_query`** — `psql -At --no-psqlrc -v ON_ERROR_STOP=1` gegen
   `${POSTGRES_DB}@${POSTGRES_HOST}`. Ein fehlgeschlagener Aufruf ist
   `fail_stage`, kein stilles Überspringen: pg_dump lief unmittelbar davor
   erfolgreich, eine nicht befragbare DB ist also selbst ein Befund.
2. **Stufe 3 (Tabellen-Store)** — vor der Schleife die erwarteten relativen
   Pfade aus `wa_table` holen; nach der Schleife jeden erwarteten Pfad gegen
   `${src}` prüfen. Fehlt einer ⇒ `fail_stage` ⇒ rot ⇒ kein Heartbeat ⇒
   `--tag incomplete` (bestehende Mechanik, keine neue).
3. **Verwaisten-Sweep nur bei gesunder Stufe** (Punkt 4 der Karte). Heute
   löscht er den letzten guten Spiegel in genau dem Lauf, der scheitert.
   Getrennt wird dabei: `.scratch.*`-Reste werden **immer** geräumt (sie sind
   nie ein letzter guter Stand), echte Verwaiste **nur**, wenn die Stufe grün
   ist.
4. **Stufe 2 (Objekt-Store)** — `--delete` auf einem leeren oder falschen
   Bucket ist dieselbe Klasse. Bei nichtleerem `wa_blob`-Katalog wird das
   Bucket-Inventar **vor** dem Sync gezählt; ist es kleiner als der Katalog,
   läuft der Sync gar nicht erst (der Spiegel bleibt unberührt). Nach dem
   Sync zusätzlich der Spiegel gegen den Katalog — das fängt einen Sync, der
   Exit 0 lieferte, aber nichts übertrug.

## 4. Tests (`deploy/hetzner/tests/test_backup_alarm.sh`)

Neue Fälle, eingefügt **vor** dem Namespace-Block (der bei fehlendem `unshare`
mit `exit 0` abbricht — dahinter wäre ein neuer Fall auf gehärteten Images
stumm):

- **12** Leerer Tabellen-Store bei nichtleerem Katalog ⇒ Exit 1, 0 Pings,
  `--tag incomplete`, **Spiegel NICHT geräumt** (der Snapshot aus dem Vorlauf
  liegt danach noch da und ist lesbar).
- **13** Legitimer Leerfall (leerer Katalog + leerer Store) ⇒ Exit 0, 1 Ping,
  `--tag dump`.
- **14** Leerer Bucket bei nichtleerem `wa_blob`-Katalog ⇒ rot, und der
  Blob-Spiegel des Vorlaufs ist noch da (`--delete` lief nicht).

Dazu ein `psql`-Stub, dessen Antworten je Fall über Env gesetzt werden, und
eine Erweiterung des `aws`-Stubs um `s3 ls`.

Alte Fälle 12/13/14 werden zu 15/16/17 umnummeriert.

## 5. Doku

- `deploy/hetzner/RUNBOOK.md` — Abschnitt zum Soll-Ist-Abgleich: was rot wird,
  warum, und was der Operator prüft (Mount, Bucket-Name, `WHO2BE_TABLESTORE_DIR`).
- `docs/adr/0011-backup-gpg-restic-offsite.md` — Nachtrag: zweite
  Wahrheitsquelle, verworfene Alternativen, Grenze.
- `changelog.d/` — Fragment (`.fixed.md`).

## 6. Verifikation

- `bash -n` auf beide Skripte
- `shellcheck` (uvx shellcheck-py) auf beide, Exit 0
- `bash deploy/hetzner/tests/test_backup_alarm.sh` — alle Fälle grün
- Negativnachweis: die neuen Fälle 12 und 14 gegen `a2bf65df` (Vorfassung)
  laufen lassen — sie müssen dort **rot** sein, sonst sind sie kein
  Regressionsschutz.
- PR gegen `main`, CI grün.

## 7. Fortschritt

- [x] Befund reproduziert
- [x] Design-Weiche entschieden und belegt
- [x] `backup.sh`: `catalog_query` + Stufe-3-Abgleich
- [x] `backup.sh`: Sweep-Gate
- [x] `backup.sh`: Stufe-2-Abgleich
- [x] Tests 12–14 + psql-Stub, Umnummerierung
- [x] Negativnachweis gegen die Vorfassung
- [x] RUNBOOK / ADR-0011 / Changelog
- [x] shellcheck + Suite grün, PR
