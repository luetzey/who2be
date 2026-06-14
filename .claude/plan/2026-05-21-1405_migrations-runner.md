# Plan — Migrations-Runner + schema_migrations

> Code-Task-Flow, Phase 2. Living document.
> Notion-Task: „Migrations-Runner + schema_migrations-Tabelle" (PROJ-19, P0).
> Erstellt: 2026-05-21 14:05 · Branch: `claude/plan-project-VQ7T4`

## Ziel / Completion-Condition

Ein idempotenter Runner wendet nummerierte SQL-Dateien aus
`apps/api/src/who2be_api/migrations/` in Reihenfolge an und haelt den Stand in
einer `schema_migrations`-Tabelle fest. Messbar erfuellt, wenn:

- `uv run ruff check .` ohne Findings
- `uv run mypy .` fehlerfrei (strict)
- `uv run pytest -q` gruen; der Idempotenz-Integrationstest belegt:
  zweite Anwendung wendet 0 Migrationen an (skippt hier ohne DB, laeuft in CI)
- Per CLI ausfuehrbar: `uv run who2be-migrate`

## Entscheidungen

- **`schema_migrations` wird vom Runner selbst gebootstrappt**
  (`CREATE TABLE IF NOT EXISTS`), nicht als Migrations-Datei — vermeidet das
  Henne-Ei-Problem.
- **Runner-Code in `core/migrations.py`**, SQL-Dateien getrennt in
  `who2be_api/migrations/` (kein Mischen von Python und SQL).
- **Eine Transaktion pro Migrations-Datei:** SQL anwenden + Versionszeile
  schreiben atomar; ein Fehlschlag laesst keine halbe Migration zurueck.
- **Keine echten Domain-Migrationen in dieser Task** — die Tabellen
  (api_token, persona, …) gehoeren zu TID 175/176. Der Idempotenz-Test nutzt
  eine temporaere Selbsttest-Migration.
- **CLI** als Console-Script `who2be-migrate` (`[project.scripts]`).

## Schritte

1. **`who2be_api/migrations/README.md`** — Namenskonvention `NNNN_<name>.sql`
   dokumentieren (haelt zugleich das Verzeichnis in Git).
2. **`core/migrations.py`** — `MIGRATIONS_DIR`-Konstante;
   `apply_migrations(conn, migrations_dir)` (bootstrappt `schema_migrations`,
   liest angewandte Versionen, wendet ausstehende `*.sql` sortiert an,
   liefert die Liste neu angewandter Dateinamen); `cli()`-Entrypoint.
3. **`apps/api/pyproject.toml`** — `[project.scripts]`
   `who2be-migrate = "who2be_api.core.migrations:cli"`.
4. **`tests/test_migrations.py`** — `@pytest.mark.integration`: temporaere
   Migration, zweimal anwenden, erste Anwendung == 1 Datei, zweite == leer;
   Cleanup. Skippt ohne erreichbare DB.

## Betroffene Dateien

- `apps/api/src/who2be_api/migrations/README.md` (neu)
- `apps/api/src/who2be_api/core/migrations.py` (neu)
- `apps/api/pyproject.toml` (mod)
- `apps/api/tests/test_migrations.py` (neu)

## Verifikation

ruff + mypy + pytest lokal, Ergebnis transkript-sichtbar. Idempotenz-Test
skippt ohne DB (diese Session) — die echte Pruefung laeuft im CI-postgres-Job.

## Status

- [x] Schritt 1–4 abgeschlossen.
- [x] Verifiziert 2026-05-21: `ruff` clean, `mypy` strict clean (14 Dateien),
  `pytest` 3 passed / 2 skipped (Idempotenz-Test skippt ohne DB).
  CLI `who2be-migrate` getestet: ohne DB sauberer Fehler + Exit-Code 1.
- Idempotenz gegen echte DB wird im CI-`postgres`-Job geprueft (hier keine DB).
- **Abgeschlossen.**
