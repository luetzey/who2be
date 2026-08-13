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
