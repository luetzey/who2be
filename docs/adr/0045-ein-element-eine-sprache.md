# ADR-0045 — Ein Element, eine Sprache: Workspace-Content-Sprache + Entity-locale

- Status: **Akzeptiert** (User-Freigabe 2026-07-24)
- Datum: 2026-07-24
- Kontext: Vorhaben „Sprache vertiefen", Plan
  `.claude/plan/2026-07-24-1900_sprache-vertiefen-ein-element-eine-sprache.md`,
  Issues #348–#356, PR #357. **Ersetzt den UI-/Selektions-Teil von ADR-0027**
  (dort vermerkt); Schema-Teile von ADR-0027 (Migration 0042) bleiben bestehen.

## Kontext

ADR-0027 modellierte Sprache als Achse pro *Version*: parallele DE+EN-Tracks
je Element, Multi-Checkbox beim Anlegen, `?locale=`-Varianten-Selektor
(Default `de`) auf API und MCP. In der Praxis entsprach das nicht der
Produkt-Intention: Die per-Element-Sprachauswahl wirkte als Fremdkörper,
System-Prompt-Templates waren ganz ausgespart, und die ausgerollten
Standard-Inhalte (6 Default-Templates + Managed-Builder-Agent) existierten
nur auf Deutsch.

User-Entscheidung (2026-07-24): Sprache wird **vertieft statt entfernt** —
als durchgängiges, sichtbares Konzept:

1. **Ein Element = eine Sprache.** Jede Persona / jedes Playbook / jede
   Resource / jedes External Tool / jeder System-Prompt IST deutsch oder
   englisch — Sprache ist ein einzelnes Attribut, kein Varianten-Track.
2. **Workspace-Sprache** bei Anlage wählbar (vorbelegt aus der UI-Sprache
   `preferred_locale`), Default für neue Inhalte und Sprache der ausgerollten
   Standard-Inhalte.
3. **Output-Sprache ans LLM** automatisch (gerenderte Sprachanweisung).
4. **EN-Rollout**: alle Builder-/Template-Inhalte auch auf Englisch.
5. **Offenes Sprachen-Set**: de/en zum Start, DB-seitig offen (kein CHECK,
   Fortführung 0042), App-Schicht zentral erweiterbar (`SUPPORTED_LOCALES`).

## Entscheidung

### Datenmodell (Migration `0069`)

- `locale text NOT NULL DEFAULT 'de'` wandert auf die **Identitäts-Zeile**
  (persona, playbook, resource, external_tool, system_prompt_template).
  Backfill aus der aktiven, sonst der neuesten Version; Legacy-Multi-Track-
  Rows in Fremdsprachen werden auf `status='inactive'` konsolidiert
  (Historie bleibt).
- `workspace.content_locale text NOT NULL DEFAULT 'de'`.
- Die Status-Partial-Unique-Indices (active/draft/review) gehen von
  `(entity_id, locale)` zurück auf `(entity_id)` — max. ein Draft/Review/
  Active je Element, sprachunabhängig.
- `*_version.locale` bleibt als **Historien-Spalte** (Writes übernehmen die
  Entity-Sprache); `UNIQUE (entity_id, locale, version)` bleibt bewusst
  bestehen (Legacy-Rows können DE-v1 UND EN-v1 tragen), dafür berechnet die
  App `next_version` **global** über alle locales. Reads nutzen einen
  defensiven Tie-Break `ORDER BY version DESC, (locale = entity.locale) DESC`.

### API

- Reads sind **locale-agnostisch** (keine Varianten-Selektion); `?locale=`
  ist auf den 5 Listen-Endpoints ein optionaler **Filter** auf die
  Entity-Sprache (`LocaleFilterQuery`), auf Detail-Routen entfernt.
- Create: optionales `locale` im Body; Default = `workspace.content_locale`
  (`services/content_locale.py::resolve_content_locale`). Update mit
  gesetztem `locale` = **Sprachwechsel** (Metadaten-Update der Entity;
  Versions-Historie unangetastet).
- System-Prompt-Templates ziehen vollständig nach (Create/Update/Filter).

### MCP

- Read-Tools: `locale: str | None = None` — auf List-Tools Filter, auf
  Fetch-Tools akzeptiert-aber-ignoriert (Backward-Compat, Deprecation im
  Docstring); **alle** Antworten tragen `locale` als Top-Level-Metadatum
  (inkl. `SearchHit`, `AgentWithRenderedPrompt`).
- Write-Tools: optionales `locale`, Default = Workspace-Sprache — der
  Builder tagged damit die Sprache beim Erstellen; `transition_*`/
  `restore_*` ohne locale (Invarianten per-entity).

### LLM-Output-Sprache (`services/agent_language.py`)

Der gerenderte Agent-System-Prompt erhält zentral im Renderer eine explizite
Sprachanweisung („Antworte auf Deutsch." / "Respond in English.") aus der
Sprache des System-Prompt-Templates; `RenderContext.locale` (Datumsformate)
folgt derselben Quelle (`de-DE`/`en-US`) statt hart `de-DE`. Beide Maps sind
zentral und additiv um Sprachen erweiterbar.

### Rollout-Inhalte (`repositories/builder_content.py`)

`ContentPack` pro Sprache als SSoT der ausgerollten Inhalte (6 Templates,
Builder-Persona + Modi, 6 Builder-Playbooks, Konventions-Resource,
Agent-Definitionen); Slugs/Keys sind cross-locale stabil, Namen/Trigger/
Tags/Beschreibungen übersetzt, EN-Sidecars strukturidentisch unter
`repositories/en/`. Seeding wählt das Pack per `workspace.content_locale`
und schreibt echte locale-Werte; `sync_managed_builder_content` läuft pro
Sprache mit Workspace-Scoping (kein Cross-Locale-Bleed);
`BUILDER_CONTENT_VERSION = 12` (Bump bei Content-Änderung in irgendeiner
Sprache). Personal-Workspace leitet `content_locale` exception-sicher aus
`preferred_locale` ab (Fallback `de`).

### Web-UI

Single-Select „Sprache" (Default = Workspace-Sprache) auf den 5 New-Pages
(System-Prompts erstmals), `LocaleBadge` in Listen/Detail, Sprachfilter in
der Listen-Filterleiste, `content_locale`-Feld bei der Workspace-Anlage
(vorbelegt aus `useLocale()`), read-only in den Workspace-Settings.

## Breaking Changes

- `*Create.locales: list[str]` → `locale: str | None` (API-Body).
- `?locale=` auf Detail-Routen entfernt (FastAPI ignoriert überzählige
  Query-Params still → Alt-Clients brechen nicht hart).
- MCP-Read-Default `locale='de'` → `None` (Alt-Clients ohne explizites
  locale werden nicht mehr still auf Deutsch gefiltert).

## Verworfen

- **Default-Track-Trick** (alle Rows bleiben `de`, Sprache wählt nur die
  Seed-Bodies): keine Read-Pfad-Änderungen nötig, aber Sprache wäre nicht
  echt im Datenmodell — kollidiert mit Badge/Filter/Builder-Tagging.
- **Multi-Track sichtbar machen** (Sprachumschalter im Editor): genau die
  per-Element-Mehrsprachigkeit, die nicht gewollt ist. Parallele
  Übersetzungen eines Elements sind künftig separate Elemente; ein
  „Übersetzung anlegen"-Flow wäre additiv nachrüstbar.

## Konsequenzen

- Sprachwechsel eines Elements mit aktiver Version ändert nur Metadaten —
  Badge (Entity-Sprache) und Inhalt der aktiven Version können bis zur
  nächsten Promotion divergieren (bewusst).
- Weitere Sprachen = neuer `ContentPack` + Einträge in `SUPPORTED_LOCALES`,
  Sprachlisten (Web) und den Maps in `agent_language.py` — rein additiv.
- Migrationspfad zurück zu echten per-Element-Übersetzungs-Tracks bleibt
  offen (Versions-Spalte + Triple-Unique existieren weiter).
