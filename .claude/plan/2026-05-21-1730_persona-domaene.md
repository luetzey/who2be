# Plan — Persona-Domaene (CRUD + Versionierung)

> Code-Task-Flow, Phase 1 · Strang 3 von 6 (siehe `architecture.md` §8.1).
> Living document. Erstellt: 2026-05-21 17:30 · Branch: `claude/plan-project-VQ7T4`

## Ziel / Completion-Condition

Die API verwaltet Personae versioniert: anlegen, lesen, listen, aktualisieren
(neue Version) und Versionshistorie abrufen — alles owner-isoliert. Messbar
erfuellt, wenn:

- Endpunkte `GET/POST /v1/personas`, `GET/PUT /v1/personas/{id}`,
  `GET /v1/personas/{id}/versions`, `GET /v1/personas/{id}/versions/{n}`
  funktionieren.
- `PUT` erzeugt atomar eine neue Version (Snapshot + `current_version`-Bump).
- Jeder Zugriff filtert serverseitig nach `owner_id`; fremde Personae →
  `404`.
- `ruff` / `mypy --strict` ohne Findings; `pytest -q` gruen.
- Unit-Tests (`persona_service` mit Fake-Repo) + Integrationstests
  (`/v1/personas` inkl. Versions-Erzeugung, skippen ohne DB → CI-`postgres`).
- `security-reviewer`-Subagent hat den DB-Zugriff geprueft (Repo-Vorgabe §6).

## Quelle / verbindlich

`architecture.md` §3 (Datenmodell), §4 (repositories/services/routers), §7
(Test-Plan, AC2); Modelle aus Strang 1 (`PersonaCreate/Update/Read`,
`PersonaVersionRead`, `PersonaContent`); Schichtmuster aus Strang 2 (Auth).

## Scope-Abgrenzung

Nur die **Persona-CRUD- und Versions-Endpunkte**. Die beiden Link-Endpunkte
`GET/PUT /v1/personas/{id}/playbooks` brauchen das Playbook-Aggregat und
gehoeren zu Strang 4. Playbook selbst ist nicht Teil dieses Strangs.

## Datenmodell-Bezug

- `persona` traegt den Identitaets-Stand (`name`, `current_version`); jeder
  Inhalt liegt als `jsonb`-Snapshot in `persona_version` (ADR-0004).
- `PersonaRead` verbindet die `persona`-Zeile mit dem Inhalt der aktuellen
  Version (Join `persona_version` auf `version = current_version`).
- `created_by` einer Version ist der handelnde Owner (MVP: ein Owner).

## Komponenten

### `core/db.py` (mod)
- `jsonb`-Codec registrieren: `create_pool(..., init=_init_connection)`, im
  Callback `set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads,
  schema="pg_catalog")`. Persona ist der erste `jsonb`-Verbraucher.

### `repositories/persona_repository.py`
- `PersonaRepository` (`Protocol`) — `insert`, `list_by_owner`, `fetch`,
  `update`, `list_versions`, `fetch_version`.
- `PgPersonaRepository(pool)` — parametrisierte SQL; `insert`/`update` in
  einer `conn.transaction()`. `fetch`/`list` joinen die aktuelle Version.
  Owner-Filter (`owner_id = $n`) in jedem Statement. Methoden, die eine
  bestimmte Persona betreffen, liefern `None`, wenn sie nicht existiert
  oder nicht dem Owner gehoert.

### `services/persona_service.py`
- `create(owner_id, data) -> PersonaRead` — Persona + Version 1.
- `list(owner_id) -> list[PersonaRead]`.
- `get(owner_id, id) -> PersonaRead` — `None` → `404`.
- `update(owner_id, id, data) -> PersonaRead` — neue Version; `None` → `404`.
- `list_versions(owner_id, id) -> list[PersonaVersionRead]` — `404`, wenn die
  Persona nicht existiert.
- `get_version(owner_id, id, n) -> PersonaVersionRead` — `404`.

### `routers/personas.py`
- Die sechs Endpunkte; alle haengen an `get_current_user` (`owner_id`).
- `POST` → `201`. Dependency-Wiring wie bei `tokens.py` (`Annotated`).

### `main.py` (mod)
- Persona-Router registrieren.

## Entscheidungen

- **`jsonb`-Codec pool-weit** statt pro-Query-Cast — eine Stelle, sauberes
  `dict`↔`jsonb`-Mapping; gilt automatisch auch fuer Playbook (Strang 4).
- **Transaktion fuer `insert`/`update`** — Snapshot-Zeile und
  `current_version`/`updated_at` muessen konsistent zusammen geschrieben
  werden (ADR-0004; §4 „update ist atomar").
- **`None`-Konvention** in Repositories statt Exceptions — der Service
  uebersetzt `None` in `HTTPException 404`; Repositories bleiben web-frei.
- **Owner-Filter im SQL**, nicht im Service — eine fremde Persona ist schon
  fuer das Repository unsichtbar (Zero-Trust, §5).
- Schichtmuster (Router→Service→Repository) exakt wie im Auth-Strang.

## Schritte

1. `core/db.py` — `jsonb`-Codec im Pool-`init` registrieren.
2. `repositories/persona_repository.py` — Protocol + `PgPersonaRepository`.
3. `services/persona_service.py` — die sechs Operationen.
4. `routers/personas.py` — Endpunkte; in `main.py` registrieren.
5. Unit-Tests `test_persona_service.py`: alle Operationen mit In-Memory-Fake-
   Repo, inkl. `404`-Pfade.
6. Integrationstest `test_personas.py`: Create→Get→List→Update→Versions via
   FastAPI-`TestClient` gegen echte DB; belegt die Versions-Erzeugung bei
   `PUT` und die Owner-Isolation; skippt ohne DB.
7. Verifikation: `ruff`, `mypy`, `pytest`.
8. `security-reviewer`-Subagent ueber den Persona-DB-Zugriff laufen lassen;
   Findings bewerten/umsetzen.

## Betroffene Dateien

- `apps/api/src/who2be_api/core/db.py` (mod — jsonb-Codec)
- `apps/api/src/who2be_api/repositories/persona_repository.py` (neu)
- `apps/api/src/who2be_api/services/persona_service.py` (neu)
- `apps/api/src/who2be_api/routers/personas.py` (neu)
- `apps/api/src/who2be_api/main.py` (mod — Router registrieren)
- `apps/api/tests/test_persona_service.py` (neu)
- `apps/api/tests/test_personas.py` (neu — Integration)

## Verifikation

`ruff` + `mypy` + `pytest` lokal. Unit-Tests (Service mit Fake-Repo) ohne DB;
die `/v1/personas`-Integrationstests skippen lokal ohne DB und laufen im
CI-`postgres`-Job.

## Offene Punkte

- Keine — Datenmodell, Modelle und Schichtmuster stehen aus den Straengen 1–2.

## Status

- [ ] Schritt 1–8
