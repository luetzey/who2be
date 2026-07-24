# Plan: Sprache als durchgängiges Konzept — „Ein Element, eine Sprache" + Workspace-Sprache + EN-Rollout

## Context

Ursprünglicher Anstoß: Die per-Element-DE/EN-Auswahl (ADR-0027) entsprach nicht
der Intention. Nach Klärung mit dem User ist das Zielbild jetzt: Sprache wird
**vertieft**, nicht entfernt —

1. **Ein Element = eine Sprache** (User-Entscheidung): Jede Persona / jedes
   Playbook / jede Resource / jeder System-Prompt IST deutsch oder englisch.
   Sprache als einzelnes Attribut: Default aus der Workspace-Sprache, beim
   Anlegen änderbar, als Badge sichtbar, in Listen filterbar. Die parallelen
   DE+EN-Versionstracks pro Element (ADR-0027-Multi-Checkbox) entfallen.
2. **Workspace-Sprache**: bei Workspace-Anlage wählbar (vorbelegt aus der
   UI-Sprache `preferred_locale`), bestimmt Default-Sprache neuer Inhalte und
   die Sprache der ausgerollten Standard-Inhalte.
3. **Output-Sprache ans LLM** (User-Entscheidung: automatisch): der gerenderte
   System-Prompt erhält eine explizite Sprachanweisung; MCP-Reads liefern die
   Sprache als Metadatum; der Builder gibt beim Erstellen die Sprache an.
4. **EN-Builder-Content im Scope** (User-Entscheidung): englische Übersetzung
   aller ausgerollten Inhalte + locale-bewusstes Seeding/Sync in diesem
   Vorhaben.
5. **Offenes Sprachen-Set**: DB ist offen (ADR-0027, kein CHECK); App-Schicht
   startet mit de/en, zentral erweiterbar (`SUPPORTED_LOCALES`).

## Verifizierter Ist-Stand (Kurzfassung)

- ADR-0027: `locale` auf `*_version` (Migration `0042`), per-Sprache-Tracks,
  `?locale=`-Param (Default `de`) auf 4 Routern, ~25 MCP-Tools mit
  `locale='de'`. **System-Prompt-Templates wurden bewusst ausgespart** (kein
  locale in Router/Service/MCP; Writes → DB-Default `de`).
- Hartes `'de'` in Read-Pfaden: `search_repository.py:39`,
  `persona_playbook_repository.py:78`, `playbook_composition_repository.py:49`,
  `dashboard_repository.py` (Param), `versioned_repository.py`
  (Default-Sonderfälle), `version_status.py` (Transition-Filter).
- Web: `LanguageSelect` (Multi-Checkbox) + `content-languages.ts` auf den
  New-Pages von Persona/Playbook/Resource/Tool + Create-Hooks
  (`locales: ['de']`). UI-String-i18n (`src/i18n/`, `useLocale`,
  `preferred_locale`) ist separat und bleibt.
- Seeding: `workspace_repository.py` — `_DEFAULT_TEMPLATES` (6 Templates,
  BlockNote-JSON-Sidecars), `_seed_default_templates()`,
  `_seed_default_agents()` (Builder-Persona/6 Playbooks/Resource), aufgerufen
  aus `ensure_personal_workspace()` + `create()`. Boot-Sync:
  `sync_managed_builder_content()` (`main.py:100`),
  `BUILDER_CONTENT_VERSION = 11`. Builder-Playbook-Prosa enthält
  `locale='de'`-Beispielaufrufe (`builder_playbook_persona_body.json:73`).
- Übersetzungsumfang EN: 6 Template-Bodies (~35 KB), Builder-Persona+Modi
  (~28 KB), 6 Builder-Playbooks (~143 KB), Konventions-Resource (~26 KB) +
  Namen/Trigger/Tags/Beschreibungen als Konstanten.

## Architektur-Entscheidung

**Locale wandert auf die Identitäts-Zeile** (persona, playbook, resource,
external_tool, system_prompt_template): `locale text NOT NULL DEFAULT 'de'`.
Das ist die saubere Abbildung von „ein Element = eine Sprache":

- Reads werden **locale-agnostisch** (keine Varianten-Selektion mehr): Detail-/
  Current-/Active-Reads holen die neueste/aktive Version ohne locale-Filter.
  `?locale=` wird auf Listen-Endpoints zum **Filter** (Sprachfilter) umgedeutet.
- `*_version.locale` bleibt als Historien-Spalte (Writes übernehmen die
  Entity-Sprache), kein Schema-Drop → billiger Rollback.
- Die per-(entity, locale)-Partial-Unique-Indices (active/draft/review) werden
  auf per-entity zurückgebaut — sonst wären nach einem Sprachwechsel zwei
  aktive Versionen möglich.
- Sprachwechsel = Metadaten-Update auf der Identitäts-Zeile (Historie behält
  alte locale-Werte, unschädlich).
- Backfill: `entity.locale` = locale der aktuellen/neuesten Version; Elemente
  mit mehreren Tracks (per Multi-Checkbox angelegt) werden auf den Track der
  aktuellen Version konsolidiert; verwaiste Fremd-Track-Versionen bleiben als
  Historie stehen.

Verworfen: (a) „Default-Track-Trick" (alles bleibt `de`, Sprache wählt nur
Seed-Bodies) — kollidiert mit Badge/Filter/Tagging, Sprache wäre nicht echt im
Datenmodell; (b) Multi-Track-UI sichtbar machen — genau das, was der User nicht
will.

## Arbeitspakete (Reihenfolge = Abhängigkeit; nach Freigabe als GitHub-Issues)

### WP1 — Models (`packages/models`)
- `workspace.py`: `WorkspaceCreate.content_locale: ContentLocale = 'de'`
  (Validator: `normalize_locale` + Mitgliedschaft in `SUPPORTED_LOCALES`);
  `WorkspaceRead.content_locale`.
- Persona/Playbook/Resource/ExternalTool: `*Create.locales: list` →
  `locale: ContentLocale | None = None` (None → Workspace-Default);
  `*Read.locale` bleibt/kommt auf Top-Level. `*Update` erlaubt Sprachwechsel.
- **System-Prompt-Template zieht nach**: `locale` auf Create/Read/Update.
- Tests: `test_locale.py` + Modell-Tests anpassen.

### WP2 — Migrationen (`0069_…`)
- `workspace.content_locale text NOT NULL DEFAULT 'de'`.
- Entity-locale: `ALTER TABLE persona/playbook/resource/external_tool/
  system_prompt_template ADD COLUMN locale text NOT NULL DEFAULT 'de'` +
  Backfill aus neuester/aktiver Version; Partial-Unique-Indices
  (active/draft/review) von `(entity_id, locale)` zurück auf `(entity_id)`;
  `UNIQUE (entity_id, locale, version)` → `UNIQUE (entity_id, version)`
  (globaler Zähler, wie bei Templates heute schon).
- Kein CHECK-Constraint (offenes Sprach-Set, wie 0042).

### WP3 — API-Read/Write-Pfade locale-agnostisch + Sprachfilter
- Router persona/playbook/resource/external_tool: `?locale=` als
  Varianten-Selektor entfernen; auf Listen-Endpoints als **Filter** behalten.
  Create: `locale` aus Body, Default `workspace.content_locale`.
- Repositories: Varianten-JOINs (`pv.locale = $locale`, max-per-locale)
  vereinfachen auf max-per-entity; `next_version` global. Harte `'de'`-Stellen
  entfernen: `search_repository.py:39`, `persona_playbook_repository.py:78`,
  `playbook_composition_repository.py:49`, `dashboard_repository.py`,
  `versioned_repository.py`-Sonderfälle. `version_status.py`: locale-Param aus
  Transitions entfernen.
- System-Prompt-Router/Service/Repo: `locale` schreiben/lesen/filtern.
- Fehler als Domain-Exception, SQL übers Repository (Leitplanke DECISIONS
  2026-07-20 beachten).

### WP4 — MCP (`apps/mcp/server.py`)
- Read-Tools: `locale`-Param bleibt akzeptiert (Backward-Compat), wird auf
  List-Tools zum Filter, auf Fetch-Tools ignoriert (deprecation-Hinweis im
  Docstring); Antworten enthalten `locale` als Metadatum.
- Write-Tools (`create_persona/playbook/resource/system_prompt/external_tool`):
  `locale`-Param (optional, Default Workspace-Sprache) — der Builder tagged
  damit die Sprache. Kein neues Tool → kein neuer
  `tool_requirements`-Mapping-Eintrag nötig.

### WP5 — Output-Sprache ans LLM (Prompt-Rendering)
- Beim Rendern des Agent-System-Prompts automatisch eine Sprachanweisung
  injizieren (Quelle: locale des System-Prompt-Templates des Agenten):
  „Antworte auf Deutsch." / "Respond in English." — zentral im Renderer, nicht
  pro Template-Body. `ctx.locale` der Placeholder-Registry (Datumsformate)
  folgt derselben Quelle statt hart `de-DE`.
- `get_persona`/`fetch_agent` liefern die Sprache prominent mit.

### WP6 — Web-UI
- `LanguageSelect` (Multi-Checkbox) → Single-`Select` „Sprache" via
  `@/components/ui/*`, Default = Workspace-Sprache, auf **fünf** New-Pages
  (System-Prompt-New kommt dazu); Create-Hooks senden `locale` statt
  `locales`; `api/types.ts` nachziehen.
- Sprach-Badge in Listen + Detail (Persona/Playbook/Resource/Tool/
  System-Prompt); Sprachfilter als neue Dimension in
  `useListFilters`/`ListFilterBar`.
- Workspace-Anlage (`OrgSettingsPage`-FormSection): Feld `content_locale`,
  vorbelegt aus `useLocale()`; Anzeige in `WorkspaceSettingsPage` (read-only).
- UI-Strings in `i18n/locales/{de,en}.json`; Designsprache
  (`docs/frontend/design-language.md`) vor UI-Arbeit lesen.

### WP7 — EN-Builder-Content + Content-Packs
- Neues Modul `apps/api/.../repositories/builder_content.py`: `ContentPack`
  pro Sprache (Slug = stabiler Cross-Locale-Schlüssel; Namen/Trigger/Tags/
  Beschreibungen pro Sprache); EN-Sidecars unter `repositories/en/` mit
  identischen Dateinamen (DE bleibt flach liegen).
- Übersetzung: 6 Template-Bodies, Builder-Persona + Modi, 6 Builder-Playbooks,
  Konventions-Resource (~230 KB BlockNote-JSON; Struktur/Pills byte-identisch,
  nur Text). Trigger auf Englisch (Trigger-Hygiene wie Kommentar
  `workspace_repository.py:410` beachten).
- Builder-Prosa aktualisieren: `locale='de'`-Beispiele → sprachbewusste
  Beispiele (DE- und EN-Pack) → **`BUILDER_CONTENT_VERSION` → 12**.

### WP8 — Seeding + Sync locale-bewusst
- `ensure_personal_workspace(...)`: `content_locale` aus
  `preferred_locale` (via `me_repository`-Profil-Lookup, exception-sicher,
  Fallback `de`); `PgWorkspaceRepository.create(...)` schreibt die Spalte.
- `_seed_default_templates`/`_seed_default_agents`: Pack nach
  `workspace.content_locale`; Versions- UND Entity-Rows tragen die echte
  Sprache (`locale='en'` bei EN-Workspaces).
- `sync_managed_builder_content`: Schleife über `SUPPORTED_LOCALES`, jede
  Kandidaten-Query bekommt `JOIN workspace w ON … AND w.content_locale = $n`
  (7 Stellen — sonst Cross-Locale-Bleed). Idempotenz über (Workspace-Sprache →
  genau ein Pack).

### WP9 — Doku + Kontext-Pflege
- **ADR-0045** „Ein Element, eine Sprache + Workspace-Content-Sprache"
  (ersetzt den UI-/Selektions-Teil von ADR-0027; Status-Header von 0027
  amenden). Breaking Changes dokumentieren (`locales`-Feld weg, `?locale=`
  umgedeutet).
- `docs/frontend/i18n.md`, Migrations-README, CHANGELOG; `.claude/context/`
  (STATE immer, DECISIONS: Architektur-Entscheidung).

## Kritische Dateien

- `apps/api/src/who2be_api/repositories/workspace_repository.py` (Seeding+Sync)
- `apps/api/src/who2be_api/repositories/{search,persona_playbook,playbook_composition,dashboard,versioned}_repository.py`
- `apps/api/src/who2be_api/services/version_status.py`, `core/locale.py`
- `apps/api/src/who2be_api/routers/{personas,playbooks,resources,external_tools,system_prompts,organizations}.py`
- `packages/models/src/who2be_models/{locale,workspace,persona,playbook,resource,external_tool,system_prompt_template}.py`
- `apps/mcp/src/who2be_mcp/server.py`
- `apps/web/src/components/forms/LanguageSelect.tsx` (+ 5 New-Pages, 5 Hooks,
  `api/types.ts`, `useListFilters`/`ListFilterBar`, `OrgSettingsPage.tsx`)
- Neue Migration `apps/api/src/who2be_api/migrations/0069_*.sql`
- Neu: `apps/api/src/who2be_api/repositories/builder_content.py` + `en/`-Sidecars

## Verifikation

- Python: `uv run pytest --cov --cov-fail-under=85`, `uv run ruff check .`,
  `uv run mypy .` — inkl. neuer Tests: Seed EN-Workspace (EN-Namen/Bodies,
  Entity-locale `en`), Sync-Tests gegen Cross-Locale-Bleed, Sprachfilter-API,
  System-Prompt-locale, Renderer-Injektion („Respond in English").
- Web: `npm run lint`, `npx tsc --noEmit`, `npm run test:coverage`,
  `npm run build` — inkl. Select-Default aus Workspace-Sprache, Badge/Filter,
  Workspace-Formular-Vorbelegung.
- Manuell (docker compose): EN-Workspace anlegen → geseedete EN-Templates +
  EN-Builder sichtbar; Element mit Sprache EN anlegen → Badge/Filter;
  Agent-Prompt-Preview enthält Sprachanweisung.

## Vorgehen nach Freigabe

Per Code-Task-Flow: Plan-Datei ins Repo (`.claude/plan/2026-07-24-*_sprache-vertiefen.md`),
GitHub-Issues je WP anlegen (WP1→WP2 Fundament; WP3/WP4 nach WP1+2; WP5–WP8
teils parallel, datei-disjunkt; WP7-Übersetzung parallelisierbar), Sub-Agents
right-sized je Issue, Review-/Konsolidierungsphase mit Integrations-Tests,
dann PR auf Branch `claude/autonomous-code-agent-role-rm19eg`.
