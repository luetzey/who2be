# Datenbank-Migrationen

SQL-Migrationen fuer die Who2Be-Datenbank. Anwendung ueber den Runner in
`who2be_api/core/migrations.py` (CLI: `uv run who2be-migrate`).

## Konvention

- Eine Datei pro Migration, benannt `NNNN_<kurzbeschreibung>.sql`
  (vierstellige, fortlaufende Nummer — z. B. `0001_api_token.sql`).
- Dateien werden in aufsteigender Reihenfolge des Namens angewandt.
- Jede Datei wird in einer eigenen Transaktion angewandt und danach in der
  `schema_migrations`-Tabelle vermerkt; bereits angewandte Dateien werden
  uebersprungen (idempotent).
- Migrationen sind unveraenderlich: ist eine Datei einmal angewandt, wird sie
  nicht editiert — Korrekturen kommen als neue Migration.

Die Tabelle `schema_migrations` legt der Runner selbst an.

## Hinweise zu einzelnen Migrationen

- `0047_seed_builder_default_agent.sql` — Backfill des Default-Agenten „Builder"
  (Persona + 4 Playbooks + `agent-builder`-Template + Agent-Row) ueber alle
  Bestands-Workspaces. Spiegelt `_seed_default_agents` in
  `repositories/workspace_repository.py` — beide Schichten synchron halten.
- `0060_seed_builder_lite_agent.sql` — Backfill der schlanken Builder-Variante
  „Builder-Lite" (managed `agent-builder-lite`-Template + Agent-Row, die die
  bestehende Builder-Persona wiederverwendet) ueber alle Bestands-Workspaces.
  Fuer LLMs mit kleinem System-Prompt-Budget. Spiegelt `_DEFAULT_TEMPLATES` +
  `_seed_default_agents` in `repositories/workspace_repository.py`.
- `0063_normalize_playbook_triggers.sql` — Bestands-Normalisierung der
  Playbook-Trigger (Split `,`/`;`, trim, Dedupe case-insensitiv, Join `, `).
  Spiegelt `normalize_triggers` in `packages/models/.../playbook.py` —
  beide Schichten synchron halten.
- `0069_entity_locale_workspace_content_locale.sql` — „Ein Element, eine
  Sprache" (ADR-0045, Plan `.claude/plan/2026-07-24-1900_sprache-vertiefen-
  ein-element-eine-sprache.md`, WP2): `workspace.content_locale` +
  `locale` auf den 5 Identitaets-Tabellen (persona/playbook/resource/
  external_tool/system_prompt_template), Backfill aus der aktiven bzw.
  neuesten Version, Legacy-Multi-Track-Konsolidierung (fremdsprachige
  draft/review/active-Versionen -> `inactive`) und Rueckbau der
  Partial-Unique-Indices (active/draft/review) von `(entity_id, locale)`
  (0042/0065) auf `(entity_id)`. `*_version.locale` bleibt als
  Historien-Spalte bestehen; `UNIQUE (entity_id, locale, version)` aus
  0042/0065 bleibt bewusst erhalten (Legacy-Multi-Track-Bestand kann
  gleiche Versionsnummer in zwei Sprachen tragen). Spiegelt keine
  Anwendungsschicht (Read/Write-Pfade folgen in WP3).
