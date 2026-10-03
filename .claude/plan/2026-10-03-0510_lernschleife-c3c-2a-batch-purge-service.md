# Lernschleife C3c-2a — Stapel und Mitglieder-Purge, Schicht 1 (Service/Repository)

Karte: t_747b6718 (PM-Schnitt 2026-10-02: C3c-1a → 1b → **2a** → 2b). Router
(`POST /memories/batch`, `DELETE /members/{user_id}/memories`), Vertragsdateien
und openapi.json folgen mit C3c-2b (t_f485a023). Norm: ADR-0053 6.1
(`memory_held`), 6.4.1 „Stapel (batch)“ und „Admin-Loeschen des
Nutzergedaechtnisses (W5 = a)“.

## Outcome

- `MemoryService.batch(ctx, MemoryBatchRequest) -> MemoryBatchResult` fuehrt
  `approve | reject | confirm | delete` je Eintrag aus, mit genau der Pruefung
  der Einzelaktion; ein Teilfehler steht im Ergebnis dieses Eintrags.
- `MemoryService.purge_user_memories(ctx, user_id) -> MemoryPurgeResult`
  loescht das ganze Nutzergedaechtnis einer Person im Workspace (nur `admin`)
  und liefert nur die Anzahl.

## Dateien (8 + dieser Plan)

1. `packages/models/src/who2be_models/memory.py`: `MemoryBatchAction`,
   `MemoryBatchRequest`, `MemoryBatchResult`, `MemoryPurgeResult`,
   `MEMORY_BATCH_MAX_IDS = 100`.
2. `packages/models/src/who2be_models/errors.py`: `memory_held`.
3. `apps/api/src/who2be_api/main.py`: Titel fuer `memory_held`.
4. `apps/api/src/who2be_api/repositories/memory_repository.py`:
   `select_batch_ids` (Filterbau `_memory_where` aus C3c-1a),
   `get_batch_targets` (nur sichtbare Eintraege, `held` aus `_HELD_SQL`),
   `purge_user_memories` (Delete + `audit_log memory.user_purged` in einer
   Transaktion).
5. `apps/api/src/who2be_api/services/memory_service.py`: `batch`,
   `purge_user_memories`, Lesson-Pruefung in der Einzel-Triage.
6. `apps/api/tests/test_memory_batch_purge.py`: Service-Tests gegen Postgres.
7. `changelog.d/t-747b6718-lernschleife-c3c-2a-batch-purge.added.md`.
8. `docs/reference/openapi.json`: nur der neue `ProblemReason`-Wert (generiert,
   wie in C3b-2a).

## Vorentschiedene Weichen (PM-Kommentar 2026-10-02 auf t_238d818f, ADR)

- Genau eines von `ids` (1..100, Dubletten werden reihenfolgetreu entfernt)
  oder `filter`. Im Filtermodus ist `expected_count` Pflicht (422 im Modell);
  weicht die Trefferzahl ab: 409 `memory_batch_count_mismatch`,
  `params={count}`, nichts geaendert.
- Die Filterauswahl nutzt dieselbe Sichtbarkeit wie `GET /memories`
  (`_memory_where`): fremdes Nutzergedaechtnis wird nie ausgewaehlt.
- ID-Modus: fremdes Nutzergedaechtnis und unbekannte IDs → je Eintrag
  `memory_not_found`, auch fuer `admin` (3a). Der Inhalt fremder Eintraege
  verlaesst die DB nicht (SQL filtert vorher).
- `viewer` mit Agentengedaechtnis im ID-Modus → 403 `insufficient_role` auf
  den ganzen Aufruf, nichts geaendert. Eigenes Nutzergedaechtnis: Pruefung je
  Eintrag.
- Je Eintrag ruft der Stapel die Einzelaktion (`triage`/`triage_my`,
  `confirm`, `delete_memory`/`delete_my`) und uebersetzt deren `ApiError` in
  `{id, ok:false, reason, params}`. Zusaetzlich nur: `approve` auf einen
  zurueckgehaltenen Eintrag → `memory_held` (6.4.1).
- `note` gilt fuer `approve`/`reject` als Triage-Notiz, bei `confirm`/`delete`
  wird sie ignoriert (die Einzelaktionen kennen keine Notiz).
- Kein eigenes Mengenlimit im Filtermodus: die ADR nennt keines,
  `expected_count` traegt die Bestaetigung durch den Menschen.
- Purge: Hard-Delete aller `scope='user' AND subject_user_id=<user>` im
  Workspace, genau eine inhaltsfreie Zeile `audit_log` (`action =
  'memory.user_purged'`, `target=<user_id>`, `detail={count}`), auch bei 0.
  Nur `admin` (inkl. AAL2) und Mensch.
- Befund nebenbei: Einzel-Triage `approve` auf `lesson` lief in die DB-CHECK
  (500). Jetzt 409 `memory_transition_invalid` — sonst waere der Stapel nicht
  „dieselbe Pruefung“.

## Verifikation

- `uv run ruff check . && uv run ruff format --check . && uv run mypy .`
- `WHO2BE_REQUIRE_DB=1 uv run pytest apps/api/tests/test_memory_batch_purge.py`
- volle DoD laut CONTRIBUTING.md auf frischer DB
- Rot-Proben: Sichtbarkeit der Batch-Ziele geoeffnet, held-Pruefung entfernt,
  Count-Vergleich entfernt, viewer-Gate entfernt, Purge-Audit entfernt,
  Purge ohne subject-Bedingung.
