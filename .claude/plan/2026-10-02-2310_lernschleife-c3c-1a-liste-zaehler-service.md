# Lernschleife C3c-1a — Liste und Zähler, Schicht 1 (Service/Repository)

Karte: t_238d818f (PM-Schnitt vom 2026-10-02: C3c-1a → 1b → 2a → 2b). Der Router
(`GET /memories`, `GET /memories/counts`), die Vertragsdateien und
openapi.json folgen mit C3c-1b (t_2e50b357). Norm: ADR-0053 6.4.1
„Sichtbarkeit“, „Zähler“, „Filter held und health“.

## Outcome

`MemoryService.list_workspace_memories` liefert eine Seite (`MemoryPage`:
`items`, `next_cursor`) über alle Agenten und Status, gefiltert und
deterministisch sortiert. `MemoryService.count_workspace_memories` liefert
`total` und Facetten-Zähler je Gruppe (`MemoryCounts`). Beide nutzen
denselben Filterbau im Repository, den C3c-2a für die Stapel-Auswahl per
Filter wiederverwendet.

## Dateien (5 + dieser Plan)

1. `packages/models/src/who2be_models/memory.py`: `MemoryFilter`, `MemoryHealth`,
   `MemoryListSort`, `MemoryCountGroup`, `MemoryPage`, `MemoryCounts`,
   Grenzen (Limit 50, Health 7/30/90 Tage).
2. `apps/api/src/who2be_api/repositories/memory_repository.py`: Filterbau
   (`_MemoryWhere`), `list_visible`, `count_visible`, `count_user_memory_by_subject`.
3. `apps/api/src/who2be_api/services/memory_service.py`: Rechte, Cursor,
   Seitengrenze, Facetten.
4. `apps/api/tests/test_memory_list_counts.py`: Service-Tests gegen Postgres.
5. `changelog.d/t-238d818f-lernschleife-c3c-1a-liste-zaehler.added.md`.

## Vorentschiedene Weichen (Beleg im Repo bzw. in der ADR, PM-Kommentar 2026-10-02)

- Sortierung `newest` (Standard) oder `oldest`, Keyset auf `(created_at, id)`.
  Der Cursor ist opak und nutzt den vorhandenen Codec
  `who2be_models.pagination.encode_cursor/decode_cursor` (base64 von
  `created_at|id`). Weitere Sortierungen nennt die ADR nicht.
- `q`: Teilstring-Suche über `fact` (ILIKE, Platzhalter `%`/`_` escaped).
  Keine Vektorsuche.
- Sichtbarkeit: ab `viewer` das eigene Nutzergedächtnis, ab `editor` dazu
  `scope='agent'` aller Agenten. Fremdes Nutzergedächtnis nie, auch nicht für
  `admin` (Owner 3a). Agent-gebundene Tokens: 403 `missing_capability`.
- `group_by=subject_user_id` nur `admin` (403 `insufficient_role`), nur
  Zahlen, nur über `scope='user'`. `q` wirkt dort nicht, weil fremder Inhalt
  sonst über Zahlen abtastbar wäre.
- Agenten-Filter und -Gruppe über `COALESCE(agent_id, created_by_agent_id)`:
  beim Agentengedächtnis der Besitzer, beim Nutzergedächtnis der Einreicher
  (dort ist `agent_id` NULL, 3.1.1). Fremder Agent → `agent_not_found`.
- Warteschlange: `status=pending` schließt `lesson` aus, außer bei
  `kind=lesson` (6.4.1 „Zähler“: Dashboard und Warteschlange zählen dieselbe
  Menge). Die Facetten wenden genau diese Regel an, damit jeder Zähler gleich
  der Länge der Liste mit diesem Filter ist.
- Facetten: je Gruppe ohne den eigenen Filter. `health` ist nicht exklusiv
  (ein Eintrag kann in mehreren Kategorien stehen) und meldet alle fünf
  Schlüssel, auch mit 0. Andere Gruppen melden nur vorhandene Schlüssel;
  NULL-Schlüssel (z. B. Eintrag ohne Agent) fallen weg.
- `held`, `health` mit den Grenzen 7/30/90 Tage rechnet der Server (6.4.1).

## Verifikation

- `uv run ruff check . && uv run ruff format --check . && uv run mypy`
- `WHO2BE_REQUIRE_DB=1 uv run pytest apps/api/tests/test_memory_list_counts.py`
- volle DoD laut CONTRIBUTING.md auf frischer DB
- Rot-Proben: Sichtbarkeitsklausel entschärft (fremdes Nutzergedächtnis
  sichtbar), Lesson-Regel entfernt, Keyset-Tiebreak entfernt.
