# Plan — SQL-Migrationen Kern-Tabellen

> Code-Task-Flow, Phase 2. Living document.
> Notion-Tasks: TASK-175 (`api_token`, `persona`, `persona_version`) +
> TASK-176 (`playbook`, `playbook_version`, `persona_playbook`), beide P0.
> Erstellt: 2026-05-21 14:23 · Branch: `claude/plan-project-VQ7T4`

## Ziel / Completion-Condition

Nummerierte SQL-Migrationen unter `apps/api/src/who2be_api/migrations/`
legen die sieben Kern-Tabellen gemaess `docs/architecture.md` §3 an.
Messbar erfuellt, wenn:

- `ruff` / `mypy` ohne Findings
- `pytest -q` gruen; ein Integrationstest wendet alle Migrationen an und
  belegt, dass die sieben Tabellen existieren (skippt ohne DB, laeuft in CI)
- `uv run who2be-migrate` legt das Schema gegen eine leere DB an

## Datenmodell-Quelle

`docs/architecture.md` §3 (ER-Diagramm) ist verbindlich. Versionierung ueber
separate History-Tabellen (ADR-0004); Tabellennamen singular.

## Entscheidungen

- **Vier Migrations-Dateien**, gruppiert nach Notion-Task:
  - `0001_api_token.sql` — `api_token` (TASK-175)
  - `0002_persona.sql` — `persona` + `persona_version` (TASK-175)
  - `0003_playbook.sql` — `playbook` + `playbook_version` (TASK-176)
  - `0004_persona_playbook.sql` — `persona_playbook` (TASK-176)
- **Plain `CREATE TABLE`** (kein `IF NOT EXISTS`): der Runner garantiert
  Einmal-Anwendung; ein doppeltes Anwenden waere ein Runner-Bug und soll
  nicht stillschweigend verschluckt werden. Idempotenz liefert der Runner
  ueber `schema_migrations`.
- **`gen_random_uuid()`** als PK-Default — in Postgres 16 im Core, keine
  Extension noetig.
- **`owner_id uuid` ohne FK** — verweist auf `auth.users.id` (Supabase),
  keine lokale User-Tabelle im MVP (architecture.md §3).
- **FKs mit `ON DELETE CASCADE`** fuer Version- und Link-Tabellen.
- **`token_hash` `UNIQUE NOT NULL`** — nur der SHA-256-Hash, nie Klartext
  (ADR-0006); ein Klartext-Spalten gibt es bewusst nicht.
- Indizes: `owner_id` auf `persona`/`playbook`/`api_token`, GIN-Index auf
  `playbook.tags` fuers Tag-Filtering. Versions-Lookups deckt der
  `UNIQUE (…_id, version)`-Index ab.
- **`triggers text`** (nullable), **`tags text[] NOT NULL DEFAULT '{}'`** —
  exakt wie im ER-Diagramm.

## Schritte

1. `0001_api_token.sql` — Tabelle `api_token` + Index `owner_id`.
2. `0002_persona.sql` — `persona` + `persona_version` (FK, UNIQUE-Version).
3. `0003_playbook.sql` — `playbook` + `playbook_version` (FK, UNIQUE,
   GIN-Index auf `tags`).
4. `0004_persona_playbook.sql` — Link-Tabelle, PK `(persona_id, playbook_id)`.
5. Integrationstest in `tests/test_migrations.py`: alle Migrationen gegen die
   DB anwenden, Existenz der sieben Tabellen pruefen (skippt ohne DB).
6. Security-Check der DDL ueber den Subagent `security-reviewer`
   (Repo-Vorgabe fuer DB-Zugriff).

## Betroffene Dateien

- `apps/api/src/who2be_api/migrations/0001_api_token.sql` (neu)
- `apps/api/src/who2be_api/migrations/0002_persona.sql` (neu)
- `apps/api/src/who2be_api/migrations/0003_playbook.sql` (neu)
- `apps/api/src/who2be_api/migrations/0004_persona_playbook.sql` (neu)
- `apps/api/tests/test_migrations.py` (mod)

## Verifikation

ruff + mypy + pytest lokal. Schema-Anwendung gegen echte DB laeuft im
CI-`postgres`-Job (diese Session hat keine DB — Test skippt).

## Status

- [x] Schritt 1–6 abgeschlossen.
- [x] Security-Review (`security-reviewer`): keine kritischen Findings.
  MITTEL-Finding „Owner-Isolation von `persona_playbook` nicht DB-seitig
  erzwungen" — nach Ruecksprache mit dem User **umgesetzt**: `owner_id` +
  zwei Composite-FKs auf `persona/playbook (owner_id, id)`; dafuer je ein
  `UNIQUE (owner_id, id)` in den Eltern-Tabellen. `architecture.md` §3
  (ER-Diagramm + Hinweis) entsprechend aktualisiert.
- [x] Verifiziert 2026-05-21: `ruff` clean, `mypy` strict clean (14 Dateien),
  `pytest` 3 passed / 3 skipped (Schema-Integrationstests skippen ohne DB).
- Schema-Anwendung gegen echte DB laeuft im CI-`postgres`-Job.
- **Abgeschlossen.**
