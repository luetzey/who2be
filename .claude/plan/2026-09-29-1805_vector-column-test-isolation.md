# Plan: Test-Isolation der `*_works_without_the_vector_column`-Tests (Karte t_329b93f8)

## Befund (gemessen, 29.09.)

- `public.content_chunk.content_vector` und `public.agent_memory.content_vector`
  existieren in der geteilten Dev-DB. Die Spalte ist also NICHT dauerhaft weg.
- Die beiden Tests schlagen trotzdem reproduzierbar fehl (`UndefinedColumnError`).
- Ursache: `_HAS_VECTOR_SQL` in `content_chunk_repository.py` / `memory_repository.py`
  prueft ueber `information_schema.columns` — nicht search-path-aware. In der DB liegt
  ein Rest-Schema `rls_ab7ee4678c32` (abgebrochener Lauf von `test_rls_isolation.py`)
  mit gleichnamiger Spalte. Nach dem `DROP COLUMN` in `public` meldet die Probe weiter
  „Spalte da“, der Code schreibt/liest `content_vector` -> Fehler.
  Dieselbe Falle ist in Migration 0021 dokumentiert und dort per `pg_attribute` +
  `to_regclass` geloest.
- Zweites, strukturelles Risiko (Karten-Vermutung): die Tests droppen die Spalte im
  GETEILTEN `public`-Schema. Abbruch zwischen DROP und ADD (SIGKILL, Timeout) oder ein
  paralleler Lauf aus einem anderen Worktree hinterlaesst/sieht eine DB ohne Spalte.

## Schritte

1. Rot-Test: Unit-nahe Integrationsprobe, dass die Vektor-Probe den `search_path`
   respektiert (Fremdschema mit Spalte, eigenes ohne) — rot auf main.
2. Ursache fixen: `_HAS_VECTOR_SQL` in beiden Repositories auf
   `pg_attribute`/`to_regclass` umstellen (Muster 0021).
3. Isolation: beide Tests laufen in einem eigenen Wegwerf-Schema
   (`novec_<hex>`, Muster `test_rls_isolation.py`), `DATABASE_URL` per
   `search_path`-Parameter darauf gelenkt, Spalte dort gedroppt, Schema im
   `finally` per `DROP SCHEMA ... CASCADE` entsorgt. `public` wird nie angefasst.
   Gemeinsamer Helfer in `who2be_api.testing` (keine zweite Kopie).
4. Doku: CONTRIBUTING (Definition of Done) — Reparatur einer betroffenen lokalen DB.
5. Changelog-Fragment `changelog.d/<slug>.fixed.md`.
6. Verifikation:
   - Rot-Probe: alter Test auf Wegwerf-DB per SIGKILL mitten im Lauf abbrechen ->
     Spalte in `public` fehlt; neuer Test gleich abgebrochen -> `public` intakt.
   - Volle DoD zweimal hintereinander auf frisch migrierter Wegwerf-DB
     (`CREATE DATABASE`, kein Docker verfuegbar).
7. PR, Review-Handoff an @reviewer.

## Out of Scope

- Die geteilte Dev-DB selbst aufraeumen (Rest-Schema droppen) — destruktiv auf
  geteiltem Zustand; nur dokumentiert, nicht ausgefuehrt.
- Allgemeine Aufraeum-Logik fuer Rest-Schemata anderer Tests.
