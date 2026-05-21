# Plan — Pydantic-Models (`packages/models`)

> Code-Task-Flow, Phase 1 · Strang 1 von 6 (siehe `architecture.md` §8.1).
> Living document. Erstellt: 2026-05-21 16:10 · Branch: `claude/plan-project-VQ7T4`

## Ziel / Completion-Condition

`packages/who2be-models` enthaelt die geteilten Pydantic-v2-Modelle fuer alle
drei Aggregate (Persona, Playbook, API-Token) plus die Verknuepfung. Reine
Modelle, kein I/O. Messbar erfuellt, wenn:

- Alle Modelle aus `who2be_models` importierbar und in `__all__` exportiert.
- `ruff` / `mypy --strict` ohne Findings.
- `pytest -q` gruen; neue Unit-Tests belegen Validierung (Pflichtfelder,
  Reject von Extra-Feldern, Round-Trip Serialisierung) fuer jedes Aggregat.
- Kein Import von `asyncpg`, `fastapi` o. Ae. in `who2be_models` (Konvention:
  einzige geteilte Abhaengigkeit, nur `pydantic`).

## Quelle / verbindlich

`architecture.md` §3 (Datenmodell), §4 „packages/models", §4 Router-Tabelle
(welche Schema-Varianten die Endpunkte brauchen). Konventionen aus dem Skill
`python-conventions`.

## Schema-Inventar

Pro Aggregat ein Satz `…Create` / `…Update` / `…Read` (+ `…VersionRead` bei
versionierten Aggregaten). `…Content` typisiert das `jsonb`-Feld.

### Persona
- `PersonaContent` — typisiert `persona_version.content`.
- `PersonaCreate` — Eingabe `POST /v1/personas` (`name` + `content`).
- `PersonaUpdate` — Eingabe `PUT /v1/personas/{id}` (`name?` + `content`).
- `PersonaRead` — Antwort: `id`, `owner_id`, `name`, `current_version`,
  `content`, `created_at`, `updated_at`.
- `PersonaVersionRead` — Antwort `…/versions/{n}`: `version`, `content`,
  `created_by`, `created_at`.

### Playbook
- `PlaybookContent` — typisiert `playbook_version.content`; enthaelt auch die
  Felder, die als `type` / `tags` / `triggers` auf die `playbook`-Zeile
  denormalisiert werden (§3-Hinweis).
- `PlaybookCreate`, `PlaybookUpdate` — analog Persona.
- `PlaybookRead` — `id`, `owner_id`, `name`, `current_version`, `type`,
  `tags`, `triggers`, `content`, `created_at`, `updated_at`.
- `PlaybookVersionRead` — analog `PersonaVersionRead`.

### API-Token
- `TokenCreate` — Eingabe `POST /v1/tokens` (`name`).
- `TokenRead` — Liste/`GET`: `id`, `name`, `created_at`, `last_used_at`,
  `revoked_at`. **Kein** `token_hash`, **kein** Klartext.
- `TokenCreated` — Sonderfall der Erstellungs-Antwort: `TokenRead`-Felder
  **plus** `token` (Klartext, genau einmal zurueckgegeben, ADR-0006).

### Verknuepfung
- `PersonaPlaybookLinkSet` — Eingabe `PUT /v1/personas/{id}/playbooks`:
  `playbook_ids: list[UUID]` (setzt die Verknuepfungen vollstaendig).

## Entscheidungen

- **Pydantic v2**, `ConfigDict(extra="forbid")` auf allen Input-Modellen —
  unbekannte Felder werden abgelehnt (Konvention „Pydantic an API-Grenzen").
- **Read-Modelle** mit `from_attributes=True`, damit sie aus Repository-Rows
  (Mapping) gefuellt werden koennen.
- **Datei-Layout** in `src/who2be_models/`: `persona.py`, `playbook.py`,
  `token.py`, `links.py`; `__init__.py` re-exportiert alles und definiert
  `__all__`. (Ein Modul pro Aggregat — vermeidet eine 300-Zeilen-Datei.)
- **`…Content`-Felder**: architecture.md spezifiziert die innere Struktur des
  `jsonb`-Inhalts NICHT. Vorschlag (siehe Offener Punkt) — bis zur Bestaetigung
  bewusst schmal gehalten, damit spaetere Str?nge nicht blockiert sind.
- **Keine `owner_id` in Input-Modellen** — kommt serverseitig aus
  `get_current_user`, nie aus dem Client-Body (Auth-Strang 2).
- `__version__` bleibt in `__init__.py` erhalten (Test `test_package.py`).

## Offener Punkt — `PersonaContent` / `PlaybookContent`

Die `jsonb`-Inhaltsstruktur ist in keinem Dokument festgelegt. **Vorschlag**:

- `PersonaContent`: `description: str`, `system_prompt: str`,
  `traits: list[str] = []`.
- `PlaybookContent`: `description: str`, `body: str`,
  `type: str`, `tags: list[str] = []`, `triggers: str | None = None`
  (die letzten drei werden vom Service auf die Tabelle denormalisiert).

Vor der Umsetzung mit dem User abzustimmen — bestimmt die ganze Modell-Form.

## Schritte

1. `persona.py` — `PersonaContent`, `PersonaCreate/Update/Read`,
   `PersonaVersionRead`.
2. `playbook.py` — `PlaybookContent`, `PlaybookCreate/Update/Read`,
   `PlaybookVersionRead`.
3. `token.py` — `TokenCreate`, `TokenRead`, `TokenCreated`.
4. `links.py` — `PersonaPlaybookLinkSet`.
5. `__init__.py` — Re-Exports + `__all__`, `__version__` behalten.
6. Tests unter `packages/models/tests/`: pro Aggregat eine Datei; Pflichtfeld-
   Validierung, `extra="forbid"`-Reject, Serialisierungs-Round-Trip.
7. Verifikation: `ruff`, `mypy --strict`, `pytest -q`.

## Betroffene Dateien

- `packages/models/src/who2be_models/persona.py` (neu)
- `packages/models/src/who2be_models/playbook.py` (neu)
- `packages/models/src/who2be_models/token.py` (neu)
- `packages/models/src/who2be_models/links.py` (neu)
- `packages/models/src/who2be_models/__init__.py` (mod — Re-Exports)
- `packages/models/tests/test_persona.py` (neu)
- `packages/models/tests/test_playbook.py` (neu)
- `packages/models/tests/test_token.py` (neu)
- `packages/models/tests/test_links.py` (neu)

## Verifikation

`uv run ruff check .`, `uv run mypy .`, `uv run pytest -q` lokal — alles ohne
DB, voll lokal pruefbar (reine Modelle).

## Status

- [x] Offener Punkt geklaert: User hat „Konkrete Felder (Vorschlag)" gewaehlt
  — `PersonaContent` (description, system_prompt, traits[]) und
  `PlaybookContent` (description, body, type, tags[], triggers) wie im Plan.
- [x] Schritt 1–7 abgeschlossen.
- [x] Verifiziert 2026-05-21: `ruff` clean, `mypy` strict clean (22 Dateien),
  `pytest` 22 passed / 3 skipped.
- **Abgeschlossen.** Naechster Strang: Auth (architecture.md §8.1 Strang 2).
