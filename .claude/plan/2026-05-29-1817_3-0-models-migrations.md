# Plan 3-0 — Sync-Vorab (Models + Migrations + ADR-Update)

**Status:** ✅ Done — Commits `2aec1c9` + Follow-up `1ac25c6`, gemerged via PR #57.

- Datum: 2026-05-29
- Master-Plan: `.claude/plan/2026-05-29-1900_phase-3-ux-polish.md` — Track 0.
- Branch: `claude/confident-hopper-h7KW9` (Cloud-Branch; spiegelt
  `feat/3-0-models-migrations`).
- Commit-Ziel: `chore(models,api): Phase-3-0 — Status-Default, Playbook-Type-ENUM,
  BlockNote-Persona-Models`.

## Ziel

Vorbedingung für Tracks 3-A/B/C/D liefern: Status-Default für neue Versions
auf `draft` umstellen, `playbook.type` per CHECK auf das 6er-Set festschreiben
und die Pydantic-Models um BlockNote-Persona, Persona-Tags, PlaybookType-Enum,
Backlink-Records und das Section-Helper-Shape ergänzen — ohne den
Repository-Init-Pfad (`PgPersonaRepository.insert` & Co.) bereits anzufassen
(das ist Track A).

## Scope-Abgrenzung (NICHT in diesem PR)

- Status-Init-Code-Fix in `apps/api/.../repositories/*_repository.py`
  (hardcoded `current_status=VersionStatus.inactive` im Insert-Return) →
  Track 3-A.
- Frontend-Anpassungen (Tracks 3-B/3-C).
- Neue Endpoints (`/usages`, `/playbooks/tags`, Section-Preview) → Track 3-A.
- MCP-Tool-Schema-Erweiterung um BlockNote-Persona-Content → Phase-3-Follow-up.

## Abweichungen vom Master-Plan (mit Begründung)

1. **Migrations-Nummern:** Master-Plan nennt `0017` + `0018`. Diese Nummern
   sind in `main` schon belegt (`0017_workspace_invitation.sql`,
   `0018_api_token_role_snapshot.sql`). Wir nehmen deshalb **`0019`** +
   **`0020`**.
2. **Pydantic-Klassennamen-Aufteilung:** Heute existiert ein `PersonaContent`
   (`description`, `system_prompt`, `traits`) — er ist faktisch das, was der
   Master-Plan `PersonaVersionContent` nennt. Wir benennen die existierende
   Klasse in **`PersonaVersionContent`** um (Re-Export-Alias `PersonaContent`
   entfällt — alle Aufrufer werden mitgezogen) und führen ein **neues**
   `PersonaContent`-Schema mit `description?` + `blocks: list[ResourceBlock]`
   ein. Das vermeidet die Zwei-`content`-Felder-Verwirrung im JSON-Tree und
   matched den Master-Plan-Wortschatz wörtlich.
3. **Legacy-Feld:** Master-Plan spricht von „`properties` deprecated mit
   Default `[]`". In der Codebasis heißt das Feld `traits` (kein
   `properties`). Wir behalten `traits` mit dem bestehenden `default_factory=
   list`-Verhalten und ergänzen einen Kommentar „deprecated, kept for backward
   compat — neuer Persona-Inhalt lebt in `PersonaVersionContent.content`".

## Arbeitspakete

### 1) Migration `0019_status_default_draft.sql`

- `ALTER TABLE persona_version ALTER COLUMN status SET DEFAULT 'draft';`
- Analog `playbook_version`, `resource_version`.
- Backfill (idempotent, partial-unique-index-konform): nur die jeweilige
  `current_version`-Zeile, nur wenn `status='inactive'` und keine
  Active-Schwester existiert:

  ```sql
  UPDATE persona_version pv
     SET status = 'draft'
    FROM persona p
   WHERE pv.persona_id = p.id
     AND pv.version    = p.current_version
     AND pv.status     = 'inactive'
     AND NOT EXISTS (
         SELECT 1 FROM persona_version act
          WHERE act.persona_id = p.id
            AND act.status     = 'active'
     );
  ```

- `ALTER ... SET DEFAULT` ist idempotent. Der Backfill auch: Zweitlauf findet
  keine `status='inactive'`-Current-Rows mit gleichzeitig fehlender
  Active-Schwester mehr, weil sie im Erstlauf auf `draft` gehoben wurden.
- Die partial-unique-Indices `*_draft_uniq` aus 0011 / 0015 werden nicht
  verletzt, weil pro Entity höchstens eine `current_version`-Zeile betroffen
  ist und die Bedingung sicherstellt, dass dort noch kein Draft lag.

### 2) Migration `0020_playbook_type_check.sql`

- Backfill unbekannter `playbook.type`-Werte → `'prompt'`.
- `CHECK (type IN ('prompt','instructions','snippet','workflow','checklist','faq'))`
  per `DO $$ ... IF NOT EXISTS (SELECT 1 FROM pg_constraint ...) THEN ...`-
  Block, damit Statement-Replay ein No-op ist.
- Backfill ist idempotent (zweite UPDATE findet keine unbekannten Werte mehr).
- Index unverändert.

### 3) Models — `packages/models/src/who2be_models/`

- `persona.py`:
  - Umbenennen `PersonaContent` → `PersonaVersionContent` (Felder unverändert:
    `description`, `system_prompt`, `traits`).
  - Neu `PersonaContent` (BlockNote-Profil-Shape): `description: str = ""`
    (max 2 000), `blocks: list[ResourceBlock]` (default leer, max 2 000) —
    spiegelt `ResourceContent`-Limits.
  - `PersonaVersionContent` bekommt `content: PersonaContent | None = None`
    und `tags: list[TagStr] = Field(default_factory=list, max_length=50)`.
  - `traits` bleibt mit Kommentar „deprecated — neue UIs liefern BlockNote
    via `content`".
  - `ResourceBlock` aus `who2be_models.resource` importieren.

- `playbook.py`:
  - Neue StrEnum `PlaybookType` mit den 6 Werten.
  - `PlaybookContent.type` bleibt `str` (Backward-Compat). `PlaybookType` ist
    für Konsumenten verfügbar; das engere Typing am Wire-Schema kommt mit
    Track 3-B/A.
  - Neues `PlaybookUsage` (`persona_id: UUID`, `persona_name: str`) — Backlink-
    Record für `GET /playbooks/{id}/usages` (Track 3-A).

- `resource.py`:
  - `LinkedBlockSection` (= `ResourceLinkRead` + `section_blocks:
    list[ResourceBlock]`) — Helper-Shape für Heading-Section-Preview
    (Track 3-A/B).
  - Neues `ResourceUsage` (`playbook_id: UUID`, `playbook_name: str`,
    `block_count: int`) — Backlink-Record für `GET /resources/{id}/usages`.

- `__init__.py`: neue Symbole exportieren
  (`LinkedBlockSection`, `PersonaContent`, `PersonaVersionContent`,
   `PlaybookType`, `PlaybookUsage`, `ResourceUsage`).

### 4) Tests

- `packages/models/tests/test_persona.py`: Helpers und Tests auf
  `PersonaVersionContent` umstellen; neue Tests für `PersonaContent`
  (Defaults, Größenobergrenze über `ResourceBlock`), für `tags`-Default und
  für das optionale `content`-Feld.
- `packages/models/tests/test_playbook.py`: Test für `PlaybookType`-Enum-Werte
  und für `PlaybookUsage`-Round-Trip.
- `packages/models/tests/test_resource.py` (neu, falls noch nicht vorhanden:
  über `test_package.py` oder ähnlich) bzw. eigenes File: Round-Trip von
  `LinkedBlockSection` und `ResourceUsage`.
- `apps/api/tests/test_persona_service.py`: Helper-Konstruktor auf
  `PersonaVersionContent` umstellen. Pfad-Semantik unverändert.
- `apps/api/src/who2be_api/repositories/persona_repository.py`: nur Type-
  Annotationen/Imports auf `PersonaVersionContent` umstellen (Funktionssignatur
  bleibt austauschbar — die JSON-Shape ändert sich nicht, weil die Klassennamen
  wechseln, die Felder identisch bleiben). Logik nicht anfassen.
- `apps/api/tests/test_migrations.py`: zwei neue, integration-markierte
  Tests:
  - `test_phase30_idempotent` — alle Migrations + manuelles Replay von 0019
    und 0020 ist No-op.
  - `test_phase30_status_default_backfill` — current_version-Row ohne Active-
    Schwester wird auf `draft` gehoben; ein Neu-Insert ohne explizites `status`
    bekommt `draft` (statt vorher `inactive`).
  - `test_phase30_playbook_type_check` — bestehender `type='core'` wird auf
    `'prompt'` gemappt; ungültiger Wert bei Insert wirft
    `CheckViolationError`.

### 5) ADR-0020 erweitern

Kurzer neuer Abschnitt „Default-Status für neue Versions" im Anschluss an
„DB-Invariante":

> **Update Phase 3-0 (2026-05-29):** Neue Versions starten mit
> `status = 'draft'` (Migration `0019_status_default_draft.sql`). Bestand:
> `current_version`-Zeilen ohne Active-Schwester werden im Backfill auf
> `draft` gehoben, damit die UI sofort eine Action-Bar rendern kann. Drafts
> dürfen sich nicht doppeln — der bestehende partial-unique-index
> `*_draft_uniq` aus 0011/0015 deckt den Race ab.

## Verifikation (DoD)

- `uv sync` ohne neue Lock-Diff (kein neues Dep).
- `uv run ruff check .` & `uv run ruff format --check .` clean.
- `uv run mypy .` strict clean.
- `uv run pytest -q` grün; Integration-Migration-Tests laufen entweder mit
  DB oder werden sauber geskipped (vorhandenes `_db_reachable`-Muster).
- Manuelles `psql`-Replay der beiden Migrations gegen ein vorhandenes
  DB-Schema gibt 0 errors (Lokal — kein Hard-Gate, weil CI ohne DB läuft).

## Commit + Push

Ein Commit auf `claude/confident-hopper-h7KW9`:
`chore(models,api): Phase-3-0 — Status-Default, Playbook-Type-ENUM,
BlockNote-Persona-Models`.

Kein PR-Open in diesem Run.
