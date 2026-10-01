# Plan: Export und Import einer Organisation (Paket 1)

Karte: t_18cb3e8b. Basis: origin/main 5616fee5 (Schema nach Migration 0092).
Owner-Entscheidungen: 2026-09-30 (Mandantentrennung = b, Export/Import je Org)
und 2026-10-01 (W1 = A, W2 = A, W3 = A, W4 = B). Zuschnitt und Weichen stehen
im Kartenkommentar vom 2026-10-01.

## Ziel

Eine Organisation laesst sich mit einem Betreiber-Werkzeug vollstaendig
exportieren und in eine leere oder fremde Instanz importieren: Rueckgabe nach
Art. 28 Abs. 3 lit. g DSGVO, Wiederherstellung einer einzelnen Org, spaeter der
Umzug. ADR-0055 §4.6 und R6.

## Fertig heisst

1. `who2be-org-transfer export --org-id <uuid> --recipient <gpg-key> --output <datei|->`
   schreibt ein gpg-verschluesseltes tar-Archiv. Ohne `--recipient` startet der
   Export nicht, einen Klartext-Pfad gibt es nicht (W4 = B).
2. `who2be-org-transfer import [--input <datei|->]` liest das entschluesselte
   Archiv (Datei oder stdin, `gpg -d … | who2be-org-transfer import`).
3. Round-Trip: Export, Import in eine leere Datenbank, erneuter Export ergibt
   je Tabelle dieselbe Pruefsumme, dieselben Blobs (sha256) und dieselben
   SQLite-Dateien (sha256).
4. Import neben einer fremden Org: deren Fingerabdruck bleibt gleich, und der
   REST-Isolationslauf aus `test_tenant_isolation_api.py` laeuft zwischen
   importierter und fremder Org ohne Befund.
5. Fail-closed: ID-Kollision, abweichender Migrationsstand, manipulierte
   Pruefsumme und eine Zeile mit fremdem Mandanten brechen den Import ab; danach
   ist im Ziel nichts geschrieben (Postgres, Blobs, SQLite).

## Entscheidungen (aus dem Zuschnitt, repo-belegt)

- **Format** `who2be-org-transfer`, `format_version` 1: tar mit `manifest.json`
  zuerst, dann `postgres/<tabelle>.jsonl` (eine `to_jsonb`-Zeile je Datensatz,
  ohne generierte Spalten, sortiert), `tablestore/<ws>/<area>.sqlite`
  (konsistenter Snapshot ueber `TableStore.snapshot_to`), `blobs/<ws>/<sha256>`.
  Das Manifest traegt Spalten, Zeilenzahl und sha256 je Tabelle und Datei.
- **IDs** unveraendert; Kollision = Abbruch. Kein Remap, kein Ueberschreiben.
- **Version**: Menge der angewandten Migrationen muss gleich sein.
- **Tabellen-Klassen** (fail-closed: eine neue Tabelle ohne Klasse und ohne
  `workspace_id`/`org_id` bricht den Export ab):
  - global, nie im Archiv: `schema_migrations`, `oauth_client`,
    `processed_webhook_event`, `account_deletion`.
  - Zugangsdaten, nie im Archiv (W3 = A): `api_token`,
    `oauth_authorization_code`, `oauth_refresh_token`, `workspace_invitation`.
  - nur Export, kein Import (W1 = A): `org_entitlement`, `entitlement_history`,
    `mcp_usage`.
  - alles andere mit `workspace_id`/`org_id` bzw. `organization`/`workspace`:
    Export und Import.
- **Identitaeten** (W2 = A): `user_id`-Spalten unveraendert, kein Mapping.
- **Mandantenschutz beim Import**: jede `workspace_id` muss zu einem Workspace
  des Archivs gehoeren, jede `org_id` zur Archiv-Org; FK-Abschluss des Archivs
  wird geprueft (keine Referenz auf eine Zeile ausserhalb des Archivs).
- **Reihenfolge**: FK-topologisch aus `pg_constraint`, dazu die Trigger-
  Abhaengigkeit `status_history` → Entity-Tabellen.

## Out of Scope (Folgekarten)

- P2 Identitaets-Mapping fuer den Umzug in eine fremde Instanz (W2-B).
- P3 Self-Service-Rueckgabe fuer den Org-Admin (API, UI, i18n).
- P4 Migration aelterer Archive.
- Streaming grosser Tabellen: Paket 1 haelt die Postgres-Zeilen einer Org im
  Speicher.

## Zuschnitt (8 Dateien)

1. dieser Plan
2. `apps/api/src/who2be_api/core/org_transfer.py` — Engine + CLI
3. `apps/api/pyproject.toml` — Entry-Point `who2be-org-transfer`
4. `apps/api/tests/test_org_transfer.py` — Round-Trip, Isolation, Abbrueche, CLI/gpg
5. `apps/api/Dockerfile` — `gnupg` im Runtime-Image (W4 = B)
6. `docs/org-export-import.md` — Betreiber-Anleitung
7. `docs/adr/0055-mandantentrennung-trennungskonzept.md` — §4.6, R6, §7, §10
8. `changelog.d/org-transfer.added.md`

Nicht in diesem PR (8-Dateien-Grenze), als Folgekarte: `docs/README.md`
(Index-Eintrag), `docs/compliance/data-retention-and-erasure.md` §1 (Rueckgabe
vor dem Purge), `.claude/context/STATE.md` und `DECISIONS.md`.

## Verifikation

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy .
WHO2BE_REQUIRE_DB=1 uv run pytest apps/api/tests/test_org_transfer.py
WHO2BE_REQUIRE_DB=1 uv run pytest --cov --cov-fail-under=85 --junitxml=junit-python.xml
python3 scripts/ci/assert_skips_within_budget.py junit-python.xml
uv run python scripts/changelog_fragments.py check
uv run python scripts/check_code_refs.py .
uv run python scripts/check_effectful_tests.py --base origin/main
```

Rot-Proben: Tenant-Pruefung im Import entfernt -> Test mit fremder Zeile rot;
Kollisionspruefung entfernt -> Kollisionstest rot (Postgres-Fehler statt
Meldung, Blob/SQLite nicht unberuehrt).

## Stand 2026-10-01

- [x] Engine + CLI, Entry-Point, Dockerfile (gnupg)
- [x] Tests: 12 gruen (`test_org_transfer.py`), Isolation per `run_isolation`
- [x] Rot-Proben: `_check_tenancy` und `_check_references` je ausgeschaltet ->
      `foreign_row` und `foreign_reference` rot; wieder eingesetzt -> gruen
- [x] Doku: Betreiber-Anleitung, ADR-0055 §4.6/R6/§7/§10, Changelog
- [x] Gesamt-Suite: 2585 passed, Coverage 93 %, 0 skipped. Die 7 Fehlschlaege
      in `test_org_transfer.py` kamen daher, dass der Hintergrundlauf die
      DATABASE_URL aus `.env` nahm, also eine geteilte DB mit fremden
      Migrationen (0091_self_account_function, 0095_memory_auto_policy aus
      anderen Worktrees). Die 5 Setup-Fehler kamen von `-p no:logging`
      (kein `caplog`). Auf der eigenen DB ohne diesen Schalter sind dieselben
      Tests gruen (26 passed).
