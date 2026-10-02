# Lernschleife C3b-2a — Not-Aus, Schicht 1 (Service/Repository)

Karte: t_23808644 (PM-Schnitt B vom 2026-10-02). Router, Vertragsdateien und
openapi.json folgen in C3b-2b (t_dc59cec6). Norm: ADR-0053 6.4.1
„Notfall-Rücknahme“, 6.1 (`memory_batch_count_mismatch`).

## Outcome

`MemoryService.revoke_auto(ctx, MemoryRevokeAuto)` setzt automatisch
aktivierte, unbestätigte Einträge atomar auf `pending` zurück, je Eintrag ein
Event `auto_revoked`. `dry_run` liefert nur die Vorschau.

## Dateien (7 + dieser Plan)

1. `packages/models/src/who2be_models/memory.py`: `MemoryRevokeAuto` (Body),
   `MemoryRevokeAutoPreview` (`count, sample, hidden_count`),
   `MemoryBatchItemResult` und `MemoryRevokeAutoResult` (`results, hidden_count`).
   Die Stapel-Ergebnisform ist auch für `batch` (C3c) gedacht.
2. `packages/models/src/who2be_models/errors.py`: `memory_batch_count_mismatch`.
3. `apps/api/src/who2be_api/main.py`: Titel in `_PROBLEM_TITLES`.
4. `apps/api/src/who2be_api/repositories/memory_repository.py`: `revoke_auto`
   (Auswahl, Sperre, Zählvergleich und Rücknahme in einer Transaktion).
5. `apps/api/src/who2be_api/services/memory_service.py`: Rechte, Vorschau,
   409 bei Abweichung.
6. `apps/api/tests/test_memory_revoke_auto.py`: Service-Tests gegen Postgres.
7. `changelog.d/t-23808644-lernschleife-c3b-2a-not-aus.added.md`.

## Vorentschiedene Weichen (Beleg im Repo bzw. in der ADR)

- Auswahl: `status='active'`, `confirmed_at IS NULL`, Event `auto_activated`
  mit `since <= created_at < until` (halboffen). Filter `agent_id` greift auf
  den Einreicher (`COALESCE(created_by_agent_id, agent_id)`), weil das
  Nutzergedächtnis `agent_id IS NULL` trägt (3.1.1) und der Einreicher dort
  in `created_by_agent_id` steht.
- `count` ist die volle Trefferzahl; `hidden_count` ist ihr Anteil aus fremdem
  Nutzergedächtnis. `expected_count` wird gegen `count` geprüft.
  `sample` (≤ 5) und `results` nennen nur, was der Aufrufer sehen darf; ein
  fremder Eintrag erscheint auch nicht mit seiner ID (Owner 3a / W5: nur Anzahl).
- Atomarität: Auswahl `FOR UPDATE` (nach ID sortiert, gegen Deadlocks),
  Zählvergleich und alle Updates in derselben Transaktion. Bei Abweichung
  wird nichts geändert.
- Rechte: `editor` und Mensch; `include_other_users=true` verlangt `admin`
  (403 `insufficient_role`); `agent_id` eines fremden Workspace → `agent_not_found`.
- Ohne `dry_run` ist `expected_count` Pflicht (422 über das Modell).
- Rücknahme behält `expires_at` (Verfall läuft weiter, 3.1.3). Ein Rollback auf
  `auto_revoked` stellt den aktiven, unbestätigten Stand her (bestehender
  `restore`-Pfad aus C3a).

## Verifikation

- `uv run ruff check . && uv run ruff format --check . && uv run mypy`
- `WHO2BE_REQUIRE_DB=1 uv run pytest apps/api/tests/test_memory_revoke_auto.py`
- volle DoD laut CONTRIBUTING.md auf frischer DB
- Rot-Proben: Atomarität (Transaktion entfernt), Zählvergleich entfernt,
  fremde Einträge im `sample`/`results`.
