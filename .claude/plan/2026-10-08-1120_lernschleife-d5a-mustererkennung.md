# Lernschleife D5a — Mustererkennung deterministisch (Service + Repository)

Kanban: t_162e0b72 · ADR-0053 3.7 (Wortlaut verbindlich), 6.5 (`GET /patterns`),
Weiche M9 (= LW4, deterministisch), Anhang B (n = 3, 30 Tage).
Router und OpenAPI folgen mit D5b.

## Ziel (fertig heisst)

`PatternService.list_patterns(ctx, agent_id=None)` liefert die berechnete
Musterliste aus zwei Quellen. Kein eigenes Aggregat, keine Migration, nichts
wird aktiviert oder angelegt. Je Muster: Quelle, Agent, Element (Fall) bzw.
Lernvorschlags-Cluster, Zaehler, Beleg-IDs, Zeitraum.

## Regeln der Sicht

**Lernvorschlaege** (`memory_repository.lesson_pattern_signals`):

- Kandidaten: `kind='lesson'`, `status='pending'`, `scope='agent'`, je Agent.
- Cluster: Paare desselben Agenten, die dieselbe Aehnlichkeitspruefung wie die
  Dublettenpruefung bestehen (`similarity(fact, fact) >= MEMORY_DEDUP_SIMILARITY`
  ODER, wenn die Vektorspalte existiert und beide Vektoren gesetzt sind,
  Cosinus `>= _DEDUP_VECTOR_SIMILARITY`). Zusammenhangskomponenten
  (Single Linkage) bilden das Cluster; deterministisch sortiert.
- Zaehler: Summe von `occurrence_count` im Cluster. Muster ab Zaehler `>= n`.
  Ein einzelner Eintrag mit `occurrence_count >= n` ist ein Cluster aus einem.
- Zeitraum: fruehestes `created_at` bis juengstes Auftreten (letztes
  `merged`-Ereignis, sonst `created_at`).

**Faelle** (`case_repository.case_pattern_groups`):

- gleicher Agent, gleiche Zuordnung (je Element `(target, entity_id)`; ein Fall
  mit zwei Elementen zaehlt fuer beide), Fall angelegt in den letzten 30 Tagen,
  Status offen, Zaehler `>= n`.
- Zeitraum: fruehestes bis juengstes `created_at` der gezaehlten Faelle.

**Zahlen:** n = 3 und 30 Tage sind gesetzte Annahmen aus ADR-0053 Anhang B,
einmal als Konstanten in `who2be_models/pattern.py`.

## Vorentschiedene Weiche (im Handoff zur Bestaetigung genannt)

„offene Faelle“ (3.7, ohne Code-Schreibweise) = noch nicht abgeschlossen:
`open`, `triaged`, `in_progress`, `reopened`. Nicht: `addressed`, `verified`,
`dismissed`. Beleg: Die Zuordnung, die 3.7 verlangt, ist Pflicht fuer
`triaged` (3.3); woertlich `status='open'` liesse die Sicht genau in dem Moment
leer werden, in dem ein Fall eingeordnet wird. `addressed`/`verified`/
`dismissed` sind die Stellen, an denen ein Mensch abschliessend gehandelt hat.
Eine Konstante (`PATTERN_OPEN_CASE_STATUSES`), also eine Zeile zum Umstellen.

## Sichtbarkeit

Mensch ab `editor`, Agent-Token mit `case_triage` (6.5). Gleiche Pruefung wie
das Triagieren von Faellen: `case_service.require_triage_right` (aus der
Methode herausgezogen, eine Quelle). Agent-Token ohne geladene Policy: 403.

## Dateien (Budget 8)

1. dieser Plan
2. `packages/models/src/who2be_models/pattern.py` (neu: Modelle, Konstanten)
3. `apps/api/src/who2be_api/repositories/memory_repository.py`
4. `apps/api/src/who2be_api/repositories/case_repository.py`
5. `apps/api/src/who2be_api/services/case_service.py` (Rechtepruefung herausziehen)
6. `apps/api/src/who2be_api/services/pattern_service.py` (neu)
7. `apps/api/tests/test_pattern_service.py` (neu, echte DB)
8. `changelog.d/t-162e0b72-pattern-service.added.md`

## Tests (echte DB, Fixtures zwischen den Grenzen)

- Fall: n-1 → kein Muster, n → Muster; 31 Tage zaehlt nicht, 29 schon;
  `dismissed`/`addressed`/`verified` zaehlen nicht, `triaged`/`reopened` schon;
  anderer Agent bzw. anderes Element trennt; Fall mit zwei Elementen zaehlt
  fuer beide.
- Lernvorschlag: Zaehler 2 → kein Muster, 3 → Muster; zwei aehnliche (2 + 1)
  bilden ein Cluster, zwei unaehnliche nicht; Vektor-Zweig; `converted`/
  `rejected` zaehlen nicht und ziehen kein Cluster ueber die Schwelle; anderer
  Agent trennt; `scope='user'` fliesst nie ein (DB-CHECK + Sicht).
- Rechte: viewer 403, editor ok, Agent ohne `case_triage` 403, ohne Policy 403,
  mit `case_triage` ok; fremder Workspace unsichtbar; `agent_id`-Filter.
- Mutationsprobe je Bedingung → rot (im PR aufgefuehrt).

## Ergebnis

- 29 Tests (`apps/api/tests/test_pattern_service.py`), echte DB, gruen.
- 23 Mutanten, alle rot: Fall-Schwelle, Fenster 32/28 Tage, Zeitfilter,
  Statusfilter, `addressed` als offen, nur `open`, Gruppierung ohne Agent bzw.
  ohne `entity_id`, `agent_id`-Filter (Fall und Lernvorschlag),
  `pending`-Filter, `kind`-Filter, `scope`-Filter, Lernvorschlags-Schwelle,
  Zaehler ohne `occurrence_count`, Trigram-Schwelle lockerer und strenger,
  keine Paare, Vektor-Zweig, Paare ueber Agenten, `last_seen` ohne `merged`,
  Rechtepruefung.
- Fixture-Texte knapp ueber (0,61) und knapp unter (0,48) der Schwelle 0,6;
  der Test misst das selbst nach.
- Test-Schemata brauchen `public` im search_path (`pg_trgm`, pgvector),
  Muster `test_memory_v2_schema`.

## Verifikation

CONTRIBUTING.md §Definition of Done, Python-Teil, mit `WHO2BE_REQUIRE_DB=1`,
0 skipped.
