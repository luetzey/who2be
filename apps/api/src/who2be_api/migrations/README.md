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
