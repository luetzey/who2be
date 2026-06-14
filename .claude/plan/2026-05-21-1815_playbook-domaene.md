# Plan — Playbook-Domaene (CRUD, Filter, Persona-Verknuepfung)

> Code-Task-Flow, Phase 1 · Strang 4 von 6 (siehe `architecture.md` §8.1).
> Living document. Erstellt: 2026-05-21 18:15 · Branch: `claude/plan-project-VQ7T4`

## Ziel / Completion-Condition

Die API verwaltet Playbooks versioniert (analog Persona) inklusive
Tag-/Trigger-Filter, und Personae lassen sich mit Playbooks verknuepfen.
Messbar erfuellt, wenn:

- `GET/POST /v1/playbooks`, `GET/PUT /v1/playbooks/{id}`,
  `GET /v1/playbooks/{id}/versions`, `GET /v1/playbooks/{id}/versions/{n}`
  funktionieren; `GET /v1/playbooks` filtert ueber `?tag=` und `?trigger=`.
- `GET/PUT /v1/personas/{id}/playbooks` listet bzw. setzt die Verknuepfungen.
- `type` / `tags` / `triggers` werden bei `POST`/`PUT` aus dem Versions-
  Inhalt auf die `playbook`-Zeile denormalisiert.
- Jeder Zugriff ist owner-isoliert; fremde Playbooks/Personae → `404`.
- `ruff` / `mypy --strict` ohne Findings; `pytest -q` gruen.
- Unit-Tests (Services mit Fake-Repos) + Integrationstests (CRUD, Filter,
  Verknuepfung; skippen ohne DB → CI-`postgres`).
- `security-reviewer`-Subagent hat den DB-Zugriff geprueft (§6).

## Quelle / verbindlich

`architecture.md` §3, §4 (Router-Tabelle, services), §7 (AC2/AC3); Modelle
aus Strang 1 (`Playbook…`, `PersonaPlaybookLinkSet`); Schichtmuster und
`jsonb`-Codec aus den Straengen 2–3.

## Scope

Playbook-CRUD + Versionierung **und** die Persona-Playbook-Verknuepfung
(`persona_playbook`). Letztere wurde in Strang 3 bewusst hierher verschoben,
weil sie das Playbook-Aggregat braucht.

## Datenmodell-Bezug

- `playbook` traegt `name`, `current_version` und die aus der aktuellen
  Version **denormalisierten** Felder `type`, `tags`, `triggers` (§3); der
  vollstaendige Inhalt liegt als `jsonb`-Snapshot in `playbook_version`.
- `persona_playbook` ist eine reine Aktuell-Stand-m:n-Relation mit eigenem
  `owner_id`; die Composite-FKs erzwingen DB-seitig Owner-Gleichheit.

## Komponenten

### `repositories/playbook_repository.py`
- `PlaybookRepository` (`Protocol`) — `insert`, `list_by_owner`, `fetch`,
  `update`, `list_versions`, `fetch_version`.
- `PgPlaybookRepository(pool)` — wie `PgPersonaRepository`, zusaetzlich:
  - `insert`/`update` schreiben `type`/`tags`/`triggers` aus
    `PlaybookContent` in die `playbook`-Zeile (Transaktion, `FOR UPDATE`).
  - `list_by_owner(owner_id, tag, trigger)` — optionale Filter: `tag =
    ANY(tags)`; `triggers ILIKE '%'||$x||'%'`. Beide Filter `NULL`-tolerant
    (`$x IS NULL OR …`), parameter-gebunden.

### `services/playbook_service.py`
- `create` / `get` / `list_all(owner_id, tag, trigger)` / `update` /
  `list_versions` / `get_version` — analog `PersonaService`, `None` → `404`.

### `routers/playbooks.py`
- Die sechs Endpunkte; `GET ""` nimmt `tag` / `trigger` als Query-Parameter.

### `repositories/persona_playbook_repository.py`
- `PersonaPlaybookRepository` (`Protocol`) — `persona_belongs_to`,
  `list_linked(persona_id)`, `owned_playbook_ids(owner_id, ids)`,
  `replace_links(owner_id, persona_id, playbook_ids)`.
- `PgPersonaPlaybookRepository` — `replace_links` in einer Transaktion
  (`DELETE` alter Links + `INSERT` neuer). `list_linked` joint `playbook` +
  aktuelle Version.

### `services/persona_playbook_service.py`
- `list_links(owner_id, persona_id) -> list[PlaybookRead]` — `404`, wenn die
  Persona nicht dem Owner gehoert.
- `set_links(owner_id, persona_id, data: PersonaPlaybookLinkSet)` — prueft
  Persona-Owner; prueft, dass **alle** `playbook_ids` dem Owner gehoeren
  (sonst `404`); ersetzt dann die Verknuepfungen.

### `routers/persona_playbooks.py`
- `GET /v1/personas/{id}/playbooks`, `PUT /v1/personas/{id}/playbooks`.
- Eigene Router-Datei (Prefix `/v1/personas`), damit `routers/personas.py`
  auf Persona-CRUD fokussiert bleibt.

### `main.py` (mod)
- Router `playbooks` und `persona_playbooks` registrieren.

## Entscheidungen

- **Denormalisierung im Repository**, nicht im Service — `type`/`tags`/
  `triggers` werden direkt beim `INSERT`/`UPDATE` aus `content` gelesen; eine
  Stelle, kein Auseinanderlaufen von Zeile und Versions-Inhalt.
- **Trigger-Filter = case-insensitive Teilstring** (`ILIKE %…%`) — pragmatisch
  fuers MVP; `tag`-Filter exakt ueber `ANY(tags)`.
- **Verknuepfung als eigenes Aggregat** (Repo + Service + Router) statt
  Persona-/Playbook-Service zu vermischen — die Operation spannt beide auf.
- **`replace_links` ersetzt vollstaendig** (PUT-Semantik aus
  `PersonaPlaybookLinkSet`): leere Liste loest alle Verknuepfungen.
- **Owner-Vorpruefung der `playbook_ids`** im Service, damit ein Cross-Owner-
  Versuch ein sauberes `404` liefert statt eines DB-FK-Fehlers (500).
- Schichtmuster und `None`→`404`-Konvention wie in den Straengen 2–3.

## Schritte

1. `repositories/playbook_repository.py` — Protocol + `PgPlaybookRepository`
   inkl. Filter.
2. `services/playbook_service.py` — die sechs Operationen.
3. `routers/playbooks.py` — Endpunkte (mit `tag`/`trigger`-Query); in
   `main.py` registrieren.
4. `repositories/persona_playbook_repository.py` — Protocol + Pg-Impl.
5. `services/persona_playbook_service.py` — `list_links` / `set_links`.
6. `routers/persona_playbooks.py` — die zwei Endpunkte; in `main.py`
   registrieren.
7. Unit-Tests: `test_playbook_service.py`, `test_persona_playbook_service.py`
   mit In-Memory-Fake-Repos (inkl. `404`- und Filter-Pfade).
8. Integrationstest `test_playbooks.py`: Playbook-CRUD + Versionierung +
   Tag-/Trigger-Filter + Persona-Playbook-Verknuepfung via `TestClient`
   gegen echte DB; belegt Owner-Isolation; skippt ohne DB.
9. Verifikation: `ruff`, `mypy`, `pytest`.
10. `security-reviewer`-Subagent ueber den Playbook-/Link-DB-Zugriff;
    Findings bewerten/umsetzen.

## Betroffene Dateien

- `apps/api/src/who2be_api/repositories/playbook_repository.py` (neu)
- `apps/api/src/who2be_api/services/playbook_service.py` (neu)
- `apps/api/src/who2be_api/routers/playbooks.py` (neu)
- `apps/api/src/who2be_api/repositories/persona_playbook_repository.py` (neu)
- `apps/api/src/who2be_api/services/persona_playbook_service.py` (neu)
- `apps/api/src/who2be_api/routers/persona_playbooks.py` (neu)
- `apps/api/src/who2be_api/main.py` (mod — Router registrieren)
- `apps/api/tests/test_playbook_service.py` (neu)
- `apps/api/tests/test_persona_playbook_service.py` (neu)
- `apps/api/tests/test_playbooks.py` (neu — Integration)

## Verifikation

`ruff` + `mypy` + `pytest` lokal. Unit-Tests ohne DB; die Integrationstests
skippen lokal ohne DB und laufen im CI-`postgres`-Job.

## Offene Punkte

- Keine — Datenmodell, Modelle und Schichtmuster stehen aus den Straengen 1–3.

## Status

- [x] Schritt 1–10 abgeschlossen.
- [x] Security-Review (`security-reviewer`): keine ausnutzbare Luecke, drei
  Punkte behoben:
  - MEDIUM (TOCTOU) — `set_links` prueft Persona-/Playbook-Owner und schreibt
    jetzt in **einer** Transaktion (`FOR UPDATE` auf der Persona-Zeile); das
    Repository liefert ein `SetLinksResult`, der Service mappt es auf 404.
  - LOW — LIKE-Wildcards (`%`/`_`/`\`) im Trigger-Filter werden maskiert, der
    Filter bleibt reiner Teilstring (`ESCAPE '\'`).
  - LOW — Fehlermeldung bei unbekannten Playbooks generisch statt
    Echo der IDs.
- [x] Verifiziert 2026-05-21: `ruff` clean, `mypy` strict clean (45 Dateien),
  `pytest` 59 passed / 6 skipped (Integrationstests skippen ohne DB).
- `/v1/playbooks`-Integrationstest gegen echte DB laeuft im CI-`postgres`-Job.
- **Abgeschlossen.** Naechster Strang: MCP-Ziel-Tools (§8.1 Strang 5).
