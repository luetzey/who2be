# Lernschleife D1a: Schema Fall (Migration 0100)

Status: aktiv (Karte t_cd89fff5)
Quelle: ADR-0053 3.3, 5.2, Anhang A.2 Zeile D1; PM-Kommentar 2026-10-07 (Q1, Q2, Q6).

## Outcome

Tabellen `agent_case`, `agent_case_event`, `agent_case_element` und
`agent_case_statement` mit CHECKs, RLS, Grants und Indizes; FK
`agent_memory.converted_case_id`; Modelle `who2be_models.case`; Repository
`case_repository.py`; DB-Tests. Ohne Service, Router, MCP, Web und Compliance-Naben (D1b).

## Dateien (Budget 8)

1. `apps/api/src/who2be_api/migrations/0100_agent_case.sql` (neu)
2. `packages/models/src/who2be_models/case.py` (neu)
3. `packages/models/src/who2be_models/__init__.py`
4. `apps/api/src/who2be_api/repositories/case_repository.py` (neu)
5. `apps/api/tests/test_agent_case_schema.py` (neu)
6. `apps/api/tests/test_memory_v2_schema.py`: der FK verlangt jetzt einen echten Fall
7. `apps/api/tests/test_memory_auto_policy.py`: wie 6
8. `changelog.d/t-cd89fff5-lernschleife-d1a-fall-schema.added.md`

## Entscheidungen (mit Beleg)

- Der Status ist abgeleitet und hat keine Spalte (ADR 3.3, „abgeleitet aus dem letzten
  `agent_case_event`“). Das Anlegen schreibt das Event `reported` (= `open`).
  Die Event-Zeit wird mit `clock_timestamp()` gesetzt, damit mehrere Events
  in einer Transaktion eine feste Reihenfolge haben.
- Ereigniswerte: die Übergänge aus 3.3 plus `reported`, `element_assigned`,
  `element_unassigned` und `statement` (Delta-Spec Phase D, Ereignis-Keys).
- `agent_case_event` bekommt zusätzlich `element_target` und `element_entity_id`.
  Begründung: ADR 3.3 sagt, „das Event `element_unassigned` hält es fest“. Dafür
  muss das Event das Element kennen.
- DB-CHECKs an Events: `addressed` verlangt eine Version (F-W6), `in_progress`/`verified`
  verlangen `measure_id`, `reopened`/`dismissed` eine Begründung. Ein Agent darf nie
  `addressed`, `verified` oder `dismissed` setzen (F-W7). Das ist Defense-in-Depth, die
  Prüfung bleibt im Service.
- Grants: Event und Schilderung sind append-only. `agent_case` bekommt SELECT, INSERT
  und DELETE (Q6: Löschen ab editor, Hard-Delete samt Verlauf, inhaltsfreie
  `audit_log`-Zeile `case.deleted` wie G3/M5). `agent_case_element` bekommt SELECT,
  INSERT und DELETE (3.3: „Löschen erlaubt“).
- Schilderung: `agent_id` muss gleich `agent_case.agent_id` sein. Das sichert ein
  Composite-FK auf `agent_case (workspace_id, id, agent_id)`.
- `converted_case_id` und `source_memory_id`: Composite-FKs über
  `(workspace_id, agent_id, …)`. Der Lernvorschlag und der Fall gehören damit zum selben
  Agenten. Das Löschen eines Agenten räumt beides in einer Anweisung ab.
  Zusätzlicher CHECK `converted_case_id IS NULL OR kind = 'lesson'` (ADR 3.1: „nur für
  `lesson`“); damit greift der FK immer vollständig. ON DELETE NO ACTION, weil
  SET NULL den CHECK `converted ⇔ converted_case_id` aus 0091 bräche.
  Offen für D2: Was passiert beim Löschen eines Falls, aus dem ein Lernvorschlag wurde?
- `source_feedback_id`: Composite-FK auf `agent_feedback (workspace_id, id)` mit
  ON DELETE SET NULL. Das Alt-Feedback ist hart löschbar (0058).
- Liste: Keyset-Cursor `(created_at, id)` plus `count_by_status` (Q1).

## Verifikation

- `WHO2BE_REQUIRE_DB=1 uv run pytest apps/api/tests/test_agent_case_schema.py
  apps/api/tests/test_memory_v2_schema.py apps/api/tests/test_memory_auto_policy.py`
- Rot-Proben: CHECK, Grant oder Filter einzeln entfernen, der Test wird rot. Die
  Ausgabe kommt in den Handoff.
- Volle DoD aus CONTRIBUTING.md.
