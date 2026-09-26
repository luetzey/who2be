# Karenzfrist im Area-Store-Sweep + ADR-0049-Nachtrag

Karte `t_5c88ac57` (Eltern: `t_ac2dab25`). Branch
`who2be/t_5c88ac57-tabellen-store-karenzfrist-im-purge-swee`, Basis
`origin/main` @ `a2bf65df`.

## Ziel (messbare Completion-Condition)

`cleanup_deleted_area_stores` loescht eine Area-Datei nur, wenn die jüngste
Schreibspur aus `{.sqlite, -wal, -shm}` aelter als `AREA_STORE_GRACE` ist.
Belegt durch drei neue Tests in `apps/api/tests/test_purge_service.py`, von
denen einer (nur `-wal` frisch) rot wird, wenn das Frische-Mass auf die
Haupt-Datei verkuerzt wird. ADR-0049 und RUNBOOK tragen den Messbefund.

Entscheidung (Karenzfrist ueber `mtime`, kein Lock) ist vom PM gesetzt und
wird nicht neu verhandelt.

## Befund vor der Umsetzung (Abweichung von §4 der Karte)

Die Karte verlangt, im RUNBOOK die Betriebsregel „Retention-Cron und Backup
nicht parallel starten" zu korrigieren. **Diese Regel steht dort nicht.**
Gemessener Ist-Zustand von `deploy/hetzner/RUNBOOK.md` @ `a2bf65df`:

- §Tabellen-Store-Backup (Z. 1306–1407) und §Retention-Cron (Z. 1411–1443)
  enthalten kein „nicht parallel", „gleichzeitig vermeiden" o. Ae.
  (`grep -n -i "nicht parallel|gleichzeitig|zeitgleich"` → nur Z. 1354, und
  das ist die `VACUUM INTO`-Konsistenzaussage, keine Betriebsregel).
- Die Cron-Zeiten liegen ohnehin auseinander: Backup 03:15 UTC (Z. 1343),
  Purge 03:30 (Z. 1420).

Statt eine nicht existierende Zeile zu korrigieren, wird die **positive**
Aussage nachgetragen: Backup und Retention-Cron duerfen sich ueberlappen,
gemessen (`VACUUM INTO` ist ein Leser). Das ist derselbe Zweck — die Regel
soll nicht nachtraeglich entstehen — und ehrlicher als eine Scheinkorrektur.
Wird im Handoff benannt.

## Arbeitsschritte

1. `apps/api/src/who2be_api/core/purge.py`
   - `AREA_STORE_GRACE = timedelta(hours=24)` neben `ORPHAN_BLOB_GRACE`,
     mit derselben Begruendungsform. Begruendung der Hoehe: die laengste
     plausible Einzeloperation ist der Snapshot einer grossen Area, gemessen
     0,56 s auf 308 MB / 150 000 Zeilen; 24 h liegen um fuenf
     Groessenordnungen darueber und machen den Sweep unabhaengig von der
     Laufzeit einzelner Operationen — dieselbe Argumentation wie bei
     `ORPHAN_BLOB_GRACE`, deshalb derselbe Wert.
   - `cleanup_deleted_area_stores(conn, store, now=None)`; `reference`
     durch `_remove_dangling_area_files` reichen.
   - `_area_store_last_write(path)`: jüngstes `mtime` aus
     `{path, path-wal, path-shm}` als `datetime` (tz=UTC), `None` wenn keine
     Datei da ist.
   - In `_remove_dangling_area_files`: Datei innerhalb der Frist →
     `logger.info(...)`, `continue`. **Nicht** in `unknown_store_dirs`
     zaehlen (der Zaehler heisst „manuell pruefen").
   - `run_retention_sweeps` reicht `reference` durch.
2. `apps/api/tests/test_purge_service.py` — drei Tests, `tmp_path`,
   `os.utime`, kein `sleep`, DB-los ueber ein Fake-Conn-Objekt
   (`fetch`/`fetchval`), damit die Tests ohne Postgres laufen.
3. `docs/adr/0049-tabellen-store-sqlite-pro-workarea.md` — Nachtrag
   2026-09-26 mit den drei Messergebnissen, der Korrektur zum
   Leser-Charakter von `VACUUM INTO`, der Unterscheidung stiller Verlust ≠
   Korruption, der Entscheidung + Owner-Vorbehalt und der ehrlich benannten
   Grenze (Heuristik, kein Lock; Advisory-Lock bleibt offen).
   Oeffentlichkeits-Regel: Zustand und Entscheidung, **keine**
   Reproduktionsanleitung fuer den Verlustfall.
4. `deploy/hetzner/RUNBOOK.md` — §Retention-Cron: Karenzfrist-Zeile +
   Log-Meldung in der Tabelle; §Tabellen-Store-Backup: Parallelitaet
   gemessen unbedenklich.
5. `changelog.d/t5c88ac57-area-store-karenzfrist.fixed.md`.
6. DoD aus `CONTRIBUTING.md` §Definition of Done; Postgres-abhaengige
   Integrationstests lokal nicht lauffaehig → benennen, CI ist die Evidenz.

## Out of Scope (aus der Karte)

Backup-/Snapshot-Pfad (`snapshot_to`, `_connect_rw`), `busy_timeout`,
Advisory-Lock, area-affines Routing, manuelle Nachbereinigung nach
Hard-Purge.
