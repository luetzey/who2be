# GDPR-Export: Rollen-/Personenfilter fuer agent_memory + Historie (t_b9af670f)

Basis: origin/main 9e38cff7. Entscheidung PM (Kommentar 2026-10-01, folgt ADR-0053 3.1.1, Owner W5=a).

## Outcome
- `agent_memories` (scope='agent') nur fuer Anfragende mit Workspace-Rolle >= editor
  (gleiche Regel wie `MemoryService.list_memories`). viewer: leere Liste + Hinweis
  im Export-Manifest des Workspace.
- `agent_memory_event` wird nur fuer die tatsaechlich exportierten memory_ids gelesen.

## Akzeptanz
- viewer-Export: `agent_memories == []`, `export_manifest.agent_memories.included == false`
  mit Begruendung; eigenes Nutzergedaechtnis weiterhin enthalten.
- editor-Export: `agent_memories` enthalten, `included == true`.
- Zwei Mitglieder mit scope='user': keiner sieht Eintrag/Historie des anderen; die
  Event-Query liefert keine Zeile zu nicht exportierten memory_ids (Spy auf gelesene Zeilen).
- Rot-Probe: neue Tests schlagen gegen origin/main-Service fehl.

## Out of Scope
- Andere Bloecke (test_cases, knowledge_base, ...) — keine Rollenfilter-Aenderung.
- Frontend (laedt das Buendel nur als Datei).

## Verifikation
- `WHO2BE_REQUIRE_DB=1 uv run pytest apps/api/tests/test_memory_compliance.py apps/api/tests/test_gdpr_export*.py`
- `uv run ruff check . && uv run ruff format --check . && uv run mypy .`

## Schritte
1. Tests schreiben (viewer/editor, zwei Mitglieder + Event-Spy) — Rot-Probe.
2. Service: Rollen-Gate + memory_id-Filter + export_manifest.
3. Doku: data-retention-and-erasure.md §4c, Changelog-Fragment.
4. Lint/Typecheck/Tests, Branch pushen, PR.

## Befund am Rand
Punkt 2 ist heute KEIN Leck im ausgelieferten JSON: `_with_events` haengt nur Events an
exportierte Eintraege. Die fremden Events wurden aber geladen (Datenminimierung, eine
Refaktorierung von `_with_events` haette sie geleakt) — Fix ist Defense-in-Depth.
