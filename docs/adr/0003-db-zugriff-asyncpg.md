# ADR-0003 — DB-Zugriff: raw asyncpg + SQL-Migrationen

- Status: Akzeptiert
- Datum: 2026-05-21
- Kontext: Who2Be MVP (PROJ-19)

## Kontext

Die API braucht Zugriff auf Supabase-Postgres. Zu entscheiden ist die
Zugriffs-Schicht: ORM, Supabase-SDK oder direkter Treiber. Die Repo-Konvention
verlangt parametrisierte Queries und versionierte Migrationen.

## Optionen

- **A — SQLAlchemy + Alembic:** ORM-Modelle, generierte Migrationen,
  DB-agnostisch testbar. Mehr Setup und Abstraktionsschichten.
- **B — Supabase Python-Client (PostgREST):** Schnell aufgesetzt, aber
  Queries/Migrationen weniger explizit, engere Kopplung an Supabase als
  Framework.
- **C — Raw asyncpg + SQL-Migrationen:** Volle SQL-Kontrolle, schlanke
  Abhaengigkeiten, hohe Performance. Mehr Boilerplate, manuelles
  Row↔Model-Mapping.

## Entscheidung

Option C (Anwender-Entscheidung). Datenzugriff ueber `asyncpg` mit
parametrisierten Statements; Schema-Aenderungen als fortlaufend nummerierte
SQL-Dateien (`apps/api/.../migrations/NNNN_<name>.sql`), idempotent angewandt,
Stand in einer `schema_migrations`-Tabelle.

## Konsequenzen

- Volle Kontrolle ueber SQL und Schema; keine ORM-Abstraktion zwischen Code
  und DB.
- Row↔Model-Mapping ist ausschliesslich in den Repositories gekapselt und wird
  dort getestet.
- Integrationstests brauchen ein echtes Postgres (Docker-Compose-DB) — kein
  SQLite-Ersatz. Unit-Tests der Services laufen ueber Fake-Repos ohne DB.
- Mehr handgeschriebenes SQL/Boilerplate als bei einem ORM — bewusst
  akzeptiert.
