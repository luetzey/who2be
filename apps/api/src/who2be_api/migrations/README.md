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
