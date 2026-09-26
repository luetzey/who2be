# ADR-0049 — Tabellen-Store: SQLite pro WorkArea

- Status: Akzeptiert
- Datum: 2026-08-13
- Kontext: Teil des Vorhabens „Agent WorkArea + Knowledge Base" (ADR-0047);
  Plan: `.claude/plan/2026-08-13-1200_agent-workarea-knowledge-base.md`.
  Agenten brauchen strukturierte Tabellendaten (Größenordnung 10k Zeilen,
  z. B. Transaktionen) mit freiem read-only-SQL, idempotentem Import und
  harter Area-Isolation.
- Bezug: ADR-0047 (Umbrella, Area-Grant-Modell), ADR-0048 (Blob-Storage),
  ADR-0039 (Schreibrechte/Rate-Limit)

## Kontext

Agenten sollen pro Area eigene Tabellen anlegen (`create_table` mit
Schema-Allowlist), Zeilen idempotent importieren und mit **freiem SQL**
abfragen (`query_table`). Freies Agenten-SQL gegen die Mandanten-Postgres ist
ausgeschlossen — es gibt keinen vertrauenswürdigen SQL-Parser als
Sicherheitsgrenze. Gebraucht wird eine Engine, in der die Isolationsgrenze
und die Read-only-Garantie **in der Engine selbst** liegen, nicht in
App-Code, der SQL versteht.

## Optionen

- **A (gewählt): SQLite, eine Datei pro Area.** Die Datei IST die
  Isolationsgrenze — eine Query kann physisch nur die eigene Area sehen.
  Read-only als Engine-Garantie: `PRAGMA query_only=ON` +
  `Connection.set_authorizer` (Deny außer SELECT/READ/FUNCTION). Stdlib,
  kein neues Infrastruktur-Stück.
- **B: DuckDB pro Area.** Verworfen — OLAP-Gewicht ohne Nutzen bei 10k
  Zeilen; kein Äquivalent zum SQLite-Authorizer, die Read-only-Garantie
  wäre wieder App-Sache.
- **C: Postgres-Schema pro Area.** Verworfen — Isolationslücke ohne
  SQL-Parser (Cross-Schema-Referenzen in freiem SQL nicht zuverlässig
  abfangbar), dynamisches DDL bricht die Plain-SQL-Migrations-Disziplin,
  Spec-Abweichung.

## Entscheidung

1. **Layout & Zugriff:** `WHO2BE_TABLESTORE_DIR/{workspace_id}/{area_id}.sqlite`;
   stdlib `sqlite3` via `asyncio.to_thread`, WAL-Modus, ein
   `asyncio.Lock` pro Area (serialisierte Writes, parallele Reads).
2. **Read-only als Engine-Enforcement:** Query-Verbindungen laufen mit
   `PRAGMA query_only=ON` **und** `set_authorizer` (Deny außer
   SQLITE_SELECT/READ/FUNCTION). DROP/UPDATE/ATTACH/PRAGMA-Writes scheitern
   in der Engine; der Service mappt auf 403 `query_not_readonly`. Der
   **Server selbst** unterliegt dem Authorizer nicht (z. B. serverseitige
   Re-Kategorisierung nach Regel-Update, protokolliert).
3. **Katalog in Postgres, Daten in SQLite:** `wa_table` (Postgres) hält
   Schema-JSON (Spalten/Typen-Allowlist
   `text|integer|numeric|date|timestamp|boolean`), `dedupe_columns`,
   `match_column`, `category_column`; die SQLite-Datei trägt **nur Daten**.
   Damit bleiben Tenancy/RLS-Metadaten, Grants und Discovery in der
   Haupt-DB.
4. **Zeitachse:** `occurred_at` + `occurred_precision` sind Pflichtspalten
   jeder Tabelle (Timeline-Anforderung N); kein Fallback auf `now()`.
5. **Idempotenter Import:** `_dedupe_hash` (aus `dedupe_columns`) UNIQUE +
   `INSERT OR IGNORE`; Doppel-Import meldet inserted/skipped. Jede Row
   trägt `_source_artifact` (Provenance zur Roheingabe).
6. **Timeline-Merge app-seitig:** Postgres (`wa_artifact`/`kb_node`,
   `date_trunc`) und je Quelle ein SQLite-Bucket-Aggregat werden im Service
   übers Datum gemergt — kein Cross-Engine-Join, keine Kante aus bloßer
   Gleichzeitigkeit (ADR-0047).
7. **Backup:** `VACUUM INTO`-Snapshots pro Area-Datei (RUNBOOK);
   `who2be-purge` löscht SQLite-Dateien gelöschter Areas.

## Konsequenzen

- Neues Package `tablestore/{engine.py,schema.py,dedupe.py}`
  (Authorizer, query_only, WAL, per-Area-Lock, to_thread), Compose-Volume
  für `WHO2BE_TABLESTORE_DIR`.
- Migration 0078 (`wa_table`, `wa_category_rule`, `wa_source_convention`) —
  der Katalog wandert durch die normale Migrations-Kette, die
  SQLite-Dateien entstehen zur Laufzeit.
- `query_table` liefert Formate `json|markdown|csv` mit Row-Cap;
  `describe_table` (Schema, Zeilenzahl, Wertebereiche, Konventionen) ist der
  agentengerechte Einstieg; `save_query_result` friert Query + Ergebnis
  serverseitig als doc-Artifact ein (Zahlen schreibt der Server, nie das
  Modell — User-Entscheidung 7).
- Tests DB-los möglich (Engine-Tests ohne Postgres):
  DROP/UPDATE/ATTACH/PRAGMA-Write → verweigert, Dedupe-Hash,
  10k-Zeilen-Aggregat.

## Bewusst nicht entschieden / Ausblick

- **Skalierung über ~10k Zeilen hinaus** (spaltenorientierte Engine,
  DuckDB-Revisit) — erst wenn Messwerte es fordern; die Engine liegt hinter
  dem `tablestore`-Package und ist austauschbar.
- **Cross-Area-Queries** — bewusst nicht unterstützt (Datei =
  Isolationsgrenze); Aggregation über Areas ist App-/Timeline-Sache.
- **Mehr-Writer-Nebenläufigkeit** — der per-Area-Lock serialisiert Writes;
  feineres Locking nur bei nachgewiesenem Bedarf.
- **Server-seitiges Chart-Rendering** — ausdrücklich kein Ziel
  (User-Entscheidung 7); `query_table`-Formate + `save_query_result` sind
  der Ersatz.

## Nachtrag 2026-08-16 — Betriebsgrenze: genau EIN Schreib-Prozess je Area

Aufgefallen beim Beantworten der Frage „kollidiert das, wenn mehrere Agenten
gleichzeitig in eine shared Area schreiben?". Die Antwort ist nein — aber nur
unter einer Randbedingung, die dieser ADR bisher nicht ausgesprochen hat.

### Was heute schützt

1. `asyncio.Lock` pro Area-Datei (`engine.py::_lock_for`) — Writes auf dieselbe
   Area **warten** aufeinander, sie scheitern nicht.
2. WAL + `busy_timeout=5000` als zweites Netz in der Engine selbst.
3. Der Import ist von Natur aus konfliktfrei: `_dedupe_hash` UNIQUE +
   `INSERT OR IGNORE`. Zwei gleichzeitige identische Importe liefern ein
   korrektes Ergebnis (einer `inserted`, einer `skipped`).

### Was NICHT schützt

`asyncio.Lock` koordiniert **innerhalb eines Python-Prozesses**. Die
Annahme „ein Prozess" ist heute erfüllt (Dockerfile-`CMD` ohne `--workers`,
keine `replicas` in den Composes), war aber nirgends festgehalten. Sie bricht
bei drei naheliegenden Handgriffen:

- `--workers N` am Uvicorn-Kommando,
- `deploy.replicas: N` am `api`-Dienst,
- mehrere API-Container hinter einem Load-Balancer.

Dann existieren zwei Locks auf derselben Datei, und es bleibt nur
`busy_timeout`. Liegt die Datei zusaetzlich auf einem Netz-Dateisystem
(NFS/EFS), ist SQLite-Locking laut SQLite-Dokumentation ausdruecklich
unzuverlaessig. Die Folge waere **stille Korruption, kein Fehler** — genau die
Fehlerklasse, die auch der Volume-Rechte-Fehler desselben Tages hatte: eine
Randbedingung, die haelt, solange niemand das Naheliegende tut.

> **Präzisiert am 2026-09-26:** „stille Korruption" ist für den *Snapshot-*
> und den *Sweep*-Pfad zu scharf — dort entsteht gemessen ein stiller
> **Verlust** bei intakten Dateien, und ein fremder Leser ist unbedenklich.
> Siehe Nachtrag 2026-09-26. Für den hier gemeinten Fall zweier gleichzeitig
> **schreibender** Instanzen auf einem Netz-Dateisystem bleibt die Aussage
> stehen.

Das ist relevant, weil ADR-0001 horizontale Aufteilung ausdruecklich offen
haelt. Dieser ADR hat sie fuer den Tabellen-Pfad geschlossen, ohne es zu
sagen. Der Ausblick-Punkt „Mehr-Writer-Nebenlaeufigkeit" meinte Threads im
selben Prozess, nicht Instanzen.

### Entscheidung

- **Betriebsgrenze ist bindend:** genau ein API-Prozess schreibt in eine Area.
  Ein Start-Guard bricht den Boot ab, wenn Multi-Worker konfiguriert ist
  (`WEB_CONCURRENCY`/`--workers`); beide Deploy-Composes tragen den Grund am
  `api`-Dienst, ein Test faengt das Wiedereinfuegen ab.
- **Grenze des Guards:** er sieht nur den eigenen Prozessbaum. Mehrere
  Container kann kein In-Process-Check erkennen — dagegen helfen nur die
  Compose-Doku und, als naechster Schritt, ein Postgres-Advisory-Lock im
  Schreibpfad (koordiniert prozess- und containeruebergreifend, weil alle
  Instanzen dieselbe Postgres teilen). Der Advisory-Lock loest das
  Dateisystem-Problem NICHT; die Grenze bleibt.

### Korrektur der Options-Begruendung (Option C)

Die urspruengliche Verwerfung von „Postgres-Schema pro Area" mit
„Isolationsluecke ohne SQL-Parser" greift zu kurz und wird hiermit korrigiert:
Postgres erzwingt Isolation ueber **Rechte**, nicht ueber Parsing — eine Rolle
ohne `USAGE` auf fremde Schemas kommt dort nicht hin, ganz ohne dass jemand
SQL versteht (dazu `default_transaction_read_only`, `statement_timeout`,
`SET ROLE`). Technisch waere das tragfaehiger, als der ADR behauptet hat.

Der tatsaechliche Einwand fehlte: `pg_catalog` bleibt lesbar. Ein Agent
koennte damit **Tabellennamen anderer Mandanten aufzaehlen** — in einer
Multi-Tenant-Cloud ein echtes Leck, sauber nur mit einer Datenbank pro
Mandant. Die Entscheidung fuer SQLite bleibt also richtig, aber mit dieser
Begruendung statt der urspruenglichen.

### Ausblick Cloud (offen, eigener ADR)

Fuer eine horizontal skalierte Cloud-Edition ist der naheliegende Weg **nicht**
ein Engine-Wechsel, sondern **area-affines Routing**: jede Area gehoert genau
einer Instanz (konsistentes Hashing auf `area_id`). Damit bleibt die
Eigenschaft erhalten, die SQLite ueberhaupt erst zur richtigen Wahl gemacht hat
— die Datei IST die Isolationsgrenze. Alternativen (Tablestore als eigener
Dienst; anbietergebundene libSQL-Dienste) gehoeren in denselben ADR, sobald die
Cloud-Edition konkret wird.

## Nachtrag 2026-09-26 — Gemessen: der Sweep, nicht das Backup, ist das Fenster

Der Nachtrag oben liest sich so, als sei jeder fremde Prozess auf einer
Area-Datei gefährlich. Das ist für den Snapshot-Pfad **widerlegt**. Gemessen
wurde mit echten Prozessen (`multiprocessing`, sqlite 3.53.1, Python 3.11.16,
ext4, die Engine-Pfade aus `engine.py` 1:1 nachgebildet):

1. **`VACUUM INTO` ist schnell.** 0,116 s auf 41 MB / 20 000 Zeilen, 0,475 s
   auf 246 MB / 120 000, **0,559 s** auf 308 MB / 150 000. Die bis dahin
   kolportierte Größenordnung („über 5 s") war um zwei Zehnerpotenzen zu hoch.
   Auf der Zielgröße dieses ADR (~10k Zeilen) sind es ~0,1 s.
2. **`VACUUM INTO` ist ein LESER.** Gegenprobe: ein Leser hält 6 s einen
   Snapshot offen, ein Writer committet parallel durchgängig — **692 Commits,
   0 Fehler**, langsamster Commit 0,414 s, `integrity_check: ok`. Genau dafür
   ist WAL eingeschaltet. Zwei parallele Snapshots derselben Area sind
   ebenfalls unauffällig (0,306 s / 0,340 s). Das **Backup braucht also keine
   Koordination** mit dem Schreibpfad; `busy_timeout=5000` hat dabei zwei
   Größenordnungen Luft.
3. **Stiller Verlust ≠ Korruption.** Verschwindet die Datei unter einer offenen
   Verbindung, lebt der POSIX-Inode weiter: **beide** Dateien bestehen danach
   `integrity_check: ok`. Der Nachtrag 2026-08-16 spricht pauschal von „stiller
   Korruption" — für diesen Pfad ist das zu scharf. Was entsteht, ist ein
   stiller **Verlust**: der Schreibvorgang gelingt und meldet dem Agenten
   Erfolg, das Ergebnis ist danach nicht mehr erreichbar. Auch ein Entfernen
   mitten in einem laufenden `VACUUM INTO` ist harmlos — der Snapshot lief
   vollständig zu Ende (150 000/150 000 Zeilen, `integrity_check: ok`).

Damit bleibt **ein** Fenster, und es liegt nicht im Backup, sondern im
Retention-Sweep `cleanup_deleted_area_stores`: er darf eine Area-Datei nicht
entfernen, während noch auf sie geschrieben wird. Der reale Weg dorthin ist
`work_area.owner_agent_id … ON DELETE CASCADE` (Migration `0073_work_area.sql`)
— eine private Area, deren Agent gelöscht wurde.

### Entscheidung

**Karenzfrist über `mtime` (`AREA_STORE_GRACE`, 24 h), kein Lock-Mechanismus.**
Der Sweep überspringt eine Area-Datei mit kürzlicher Schreibaktivität still;
der nächste Lauf betrachtet sie erneut. Frische-Maß ist das **jüngste** `mtime`
aus `.sqlite`, `-wal` und `-shm` — im WAL-Modus liegt die Schreibspur im `-wal`,
und ein Maß nur auf der Hauptdatei wäre genau im Schreibfall wirkungslos. Die
Höhe ist dieselbe Überlegung wie bei `ORPHAN_BLOB_GRACE` in derselben Datei:
sie deckt die längste plausible Einzeloperation (0,56 s, s. o.) um
Größenordnungen ab und macht den Sweep damit unabhängig von der Laufzeit
einzelner Operationen.

Verworfen:

- **Nur dokumentieren.** Eine Betriebsregel müsste nachts ein Mensch einhalten;
  das Fenster bliebe. Bei wenigen Zeilen Aufwand ist das die schlechtere Seite
  des Tauschs.
- **`fcntl.flock` im Schreibpfad der Engine.** Läge im Hot Path jeder einzelnen
  Operation, um ein Fenster zu schließen, das höchstens einmal pro gelöschtem
  Agenten entsteht — und ist auf Netz-Dateisystemen ebenso unzuverlässig wie
  SQLite-Locking (s. o.), der Sicherheitsgewinn wäre teils nominell.
- **Postgres-Advisory-Lock im Schreibpfad.** Der richtige Weg für den
  Mehr-Container-Fall, aber ein ungleich größerer Eingriff — und er löst ein
  **anderes** Problem als das hier gemessene.
- **Änderungen am Backup-/Snapshot-Pfad.** Nach Messung 2 unnötig.

**Vorbehalt:** diese Entscheidung ist mangels erreichbarem Owner vom
Projektmanagement getroffen worden, auf Basis der Messung oben. Sie ist
revidierbar, falls der Owner den Mehr-Container-Fall (Advisory-Lock) vorziehen
will — die Karenzfrist steht dem nicht im Weg, sie ersetzt ihn nur für den
heutigen Ein-Container-Betrieb.

### Grenze der Lösung

Eine `mtime`-Karenz ist eine **Heuristik, kein Lock**. Sie schließt das Fenster
für den dokumentierten Cron-Pfad, weil der nachts gegen Areas läuft, die
tagelang niemand angefasst hat. Sie hilft **nicht** gegen zwei API-Container
und ersetzt den Postgres-Advisory-Lock nicht — der bleibt der offene Punkt aus
dem Nachtrag 2026-08-16 und wird durch die Karenzfrist nicht verbaut.
