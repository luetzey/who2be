# ADR-0027 — Content-i18n: locale pro Version

- Status: **Akzeptiert** (User-Freigabe 2026-06-04)
- Datum: 2026-06-04
- Kontext: Who2Be Welle 2, Stream D2 (i18n Content). Plan
  `.claude/plan/2026-06-04-1000_ux-fixes-i18n-embedding.md` (§D2) +
  `.claude/plan/2026-06-04-1200_i18n-content-model.md`.

## Kontext

Persona, Playbook, Resource und System-Prompt-Template sind versioniert: eine
Identitaets-Zeile (`persona`, `playbook`, …) plus unveraenderliche
jsonb-Snapshots in `*_version`-Tabellen (ADR-0004). Es gibt **kein** locale-
Feld; alle Inhalte sind implizit deutsch. Der User hat entschieden (Plan
2026-06-04): **Inhalte als echte DE+EN-Varianten**, nicht nur UI-String-i18n
(das ist Stream D1).

Vorhandene Bausteine, die i18n schon andeuten:
- `services/placeholders/registry.py` kennt `ctx.locale` (heute hart `de-DE`,
  nur fuer Datumsformatierung).
- MCP-Tools (`apps/mcp/server.py`) liefern Inhalte ohne Sprach-Parameter.

Anforderungen:
- **Mehrsprachige Inhalte:** dieselbe Persona/Playbook/Resource in DE *und* EN.
- **Backward-Compat:** Bestandsdaten = implizit `'de'`; alle Lese-Pfade ohne
  `locale`-Angabe liefern weiter Deutsch.
- **Init-Auswahl:** beim Anlegen waehlt der User eine oder mehrere Sprachen →
  die entsprechenden Sprachvarianten werden angelegt.
- **MCP/API deterministisch:** ein Konsument bekommt genau eine Variante pro
  (Entity, locale, status).

## Kern-Spannung: `current_version`

Die Versionierung haengt heute an zwei Mechanismen:

1. **Status-Reads** (MCP, `active_only`): JOIN auf `pv.status = 'active'`,
   abgesichert durch Partial-Unique-Index `(persona_id) WHERE status='active'`.
   → braucht nur einen zusaetzlichen `locale`-Filter.
2. **Current-Reads** (Editor/Default-API): JOIN auf
   `pv.version = p.current_version`. Die Identitaets-Zeile traegt **einen**
   `current_version int`.

Mit zwei Sprachen gibt es zwei parallele "aktuelle" Versionen (DE v3 / EN v2).
Eine einzelne `current_version`-Spalte kann das nicht ausdruecken — unabhaengig
davon, ob Versionsnummern global oder pro Sprache laufen. Der Content-Select
**muss** also auf "neueste Version je (Entity, locale)" umgestellt werden.

## Optionen

- **A — Eigene Identitaets-Zeile pro Sprache.** `persona` bekommt `locale`,
  DE und EN sind getrennte `persona`-Rows, verknuepft ueber eine Gruppen-ID.
  Sauber getrennt, aber: bricht alle Composite-FKs (`persona_playbook`,
  `playbook_resource_link`, `agent`-Refs zeigen auf `persona.id`), verdoppelt
  Identitaets-Metadaten (Name, owner, Tags-Lookup), und Cross-Locale-Operationen
  (Umbenennen, Loeschen) muessen N Rows synchron halten. Grosser Blast-Radius.
- **B — `locale` pro Version, Versionsnummern pro Sprache (gewaehlt).**
  Eine Identitaets-Zeile, `locale` auf `*_version`. Versions-Track pro Sprache
  (`UNIQUE (persona_id, locale, version)`), Status-Invariante pro
  (Entity, locale). Content-Reads waehlen die neueste Version je locale. Alle
  FKs/Refs bleiben unveraendert (zeigen auf die Identitaets-Zeile).
- **C — `locale` pro Version, eine globale Versionsnummer.** Wie B, aber
  `UNIQUE (persona_id, version)` bleibt global. Dann teilen sich DE/EN einen
  Zaehler (DE v1, EN v2, DE v3 …). Die Versions-Historie pro Sprache wird
  unleserlich ("warum springt DE von v1 auf v3?"), und ein Sprach-Edit
  inkrementiert den Zaehler der anderen Sprache mit. Verworfen.

## Entscheidung

**Option B.** `locale` lebt auf den `*_version`-Tabellen; jede Sprache ist ein
eigener Versions-Track; alle Refs/FKs bleiben an der Identitaets-Zeile.

### 1. Schema (Migration ab 0042)

`locale`-Spalte auf `persona_version`, `playbook_version`, `resource_version`
und `system_prompt_template_version`:

```sql
ALTER TABLE persona_version
    ADD COLUMN locale text NOT NULL DEFAULT 'de';
```

**Kein** CHECK-Constraint (User-Entscheidung 2026-06-04): das Sprach-Set bleibt
DB-seitig offen, damit weitere Sprachen ohne Migration moeglich sind. Die
Anwendungs-Schicht (Pydantic) normalisiert/validiert das Kuerzel
(lowercase, kurze Laenge) — heute bietet die UI nur `de`/`en` an.

`NOT NULL DEFAULT 'de'` fuellt **bestehende Rows automatisch** mit `'de'` —
kein separater Backfill noetig ("Bestandsdaten = implizit de").

Versions-Track pro Sprache — alte Constraint droppen, neue mit `locale`:

```sql
ALTER TABLE persona_version DROP CONSTRAINT persona_version_persona_id_version_key;
ALTER TABLE persona_version ADD CONSTRAINT persona_version_persona_id_locale_version_key
    UNIQUE (persona_id, locale, version);
```

Status-Invariante pro (Entity, locale) — Partial-Unique-Indices aus 0011/0015/
0022 droppen und um `locale` erweitern:

```sql
DROP INDEX persona_version_active_uniq;
CREATE UNIQUE INDEX persona_version_active_uniq
    ON persona_version (persona_id, locale) WHERE status = 'active';
-- analog draft_uniq, review_uniq; analog playbook/resource/template
```

`status_history` bekommt **keine** locale-Spalte in dieser Welle (Status-Audit
bleibt entity-weit; falls noetig spaeter additiv). Diese Annahme wird im
Plan als offener Punkt markiert.

### 2. Content-Selection statt `current_version`

- **Active-Reads (MCP, `active_only`):** zusaetzlicher Filter
  `AND pv.locale = $locale`. Die Status-Reads haengen schon an
  `status='active'`, nicht an `current_version` — minimaler Eingriff.
- **Current-Reads (Editor/Default-API):** JOIN-Bedingung
  `pv.version = p.current_version` wird ersetzt durch "neueste Version je
  (Entity, locale)":

  ```sql
  JOIN persona_version pv ON pv.persona_id = p.id AND pv.locale = $locale
   AND pv.version = (
       SELECT max(v.version) FROM persona_version v
       WHERE v.persona_id = p.id AND v.locale = $locale
   )
  ```

  Die zurueckgegebene `current_version` in `PersonaRead` wird auf die
  Versionsnummer **dieser** Sprache aliased (genau wie `_SELECT_ACTIVE` heute
  schon `pv.version AS current_version` macht) — `current_version` und
  `content` matchen pro Antwort.

- **`persona.current_version` (Spalte) bleibt erhalten** als Fallback fuer
  nicht-locale-bewusste Code-Pfade; sie spiegelt den Default-Locale-Track
  (`'de'`). Sie ist **nicht** mehr die Wahrheit fuer die Variantenauswahl —
  diese Rolle uebernimmt der Max-Version-je-locale-Select. So bleibt
  Rollback billig (Spalte droppen) und Bestandscode valide.

- **`next_version`** beim Schreiben (insert/update/draft/restore) wird pro
  Sprache berechnet: `max(version) WHERE persona_id=… AND locale=…) + 1`.

### 3. Models (`packages/models`)

- Neuer Typ `ContentLocale = Literal["de", "en"]` (zentral, z. B. in
  `status.py` oder neuem `locale.py`) + `DEFAULT_LOCALE = "de"`.
- `*VersionRead` (Persona/Playbook/Resource/Template) bekommt `locale:
  ContentLocale = "de"` (Default deckt Bestand + alte Clients additiv).
- `*Create` bekommt `locales: list[ContentLocale] = ["de"]` (min. 1, eindeutig)
  → Init-Auswahl. Der mitgelieferte `content` ist die Vorlage; jede gewaehlte
  Sprache startet als eigene Draft-v1 (Initial-Copy = Startpunkt fuer die
  Uebersetzung; reine Sprach-Verfeinerung passiert danach im Editor pro
  locale).
- `*Update`/Draft-Pfade tragen das Ziel-`locale` (Query-Param, nicht Body) —
  eine PUT/PATCH-Operation betrifft genau eine Sprachvariante.

### 4. API-Router

- **Lesen** (`GET .../personas`, `.../personas/{id}`, `…/versions`,
  `…/versions/{v}`): optionaler Query-Param `?locale=de|en`, Default `de`.
- **Anlegen** (`POST`): `locales` aus dem Body → Service legt N Varianten an.
- **Aendern** (`PUT`/`PATCH .../draft`/`restore`/`transition`): `?locale=`,
  Default `de`. Status-Transitions laufen pro (Entity, locale).
- Validierung: unbekanntes locale → 422 (durch `Literal`).

### 5. MCP (`apps/mcp/server.py`)

`get_persona`, `fetch_playbook`, `fetch_resource`, `list_playbooks`,
`list_resources` bekommen `locale: str = "de"`. Der Wert wird als `?locale=`
an die API durchgereicht; die Tools filtern weiterhin server-seitig auf
`status='active'`. Default `"de"` ⇒ Backward-Compat fuer bestehende MCP-Clients.

### 6. Frontend (Create-Flows)

- Sprach-Auswahl (Multi-Select DE/EN) in den Create-Dialogen von
  Persona/Playbook/Resource → `locales` im POST-Body.
- Lese-/Editor-Flows reichen `locale` als Query-Param durch. Die Quelle der
  aktiven Sprache (User-Pref) wird mit Stream D1 abgestimmt; bis D1 steht,
  ist `de` der harte Default (kein Bruch).

## Konsequenzen

- **Additiv & rueckwaerts-kompatibel:** `DEFAULT 'de'` + Default-Param `de`
  ⇒ alle bestehenden Clients und Daten verhalten sich unveraendert.
- **Refs/FKs unangetastet:** `persona_playbook`, `playbook_resource_link`,
  `*_composition`, `agent`-Refs zeigen auf die Identitaets-Zeile — kein
  Aufwand, kein Blast-Radius (Vorteil gegenueber Option A).
- **Versions-Historie pro Sprache lesbar** (DE v1→v2, EN v1→v2 getrennt).
- **`current_version`-Spalte verliert die Auswahl-Hoheit.** Code, der
  `p.current_version` direkt liest und implizit "das ist DER aktuelle Inhalt"
  annimmt, sieht nur noch den `'de'`-Track. Betroffene Stellen werden im Plan
  einzeln auditiert (persona/playbook/resource/composition/agent-Repos).
- **Block-Refs / Section-Slices** (Playbook→Resource) sind locale-blind: ein
  `block_id`-Ref trifft in der Ziel-locale-Variante denselben Block nur, wenn
  die Uebersetzung die Block-IDs erhaelt. In dieser Welle wird Resolution
  innerhalb derselben locale aufgeloest; cross-locale-Refs sind out of scope
  (im Plan als Risiko notiert).
- **Rollback billig:** `locale`-Spalten + neue Indices droppen, alte
  `(persona_id)`-Indices und `(persona_id, version)`-Constraint
  wiederherstellen; Inhalte bleiben unangetastet.
- **status_history ohne locale:** Status-Audit ist entity-weit; pro-locale-
  Audit kann spaeter additiv nachgezogen werden.

## Freigabe (User-Entscheidungen 2026-06-04)

Der Review-Stop aus SCHRITT 0 ist abgeschlossen. Entschieden:
1. **Option B** — locale pro Version (nicht A).
2. **Versions-Track pro Sprache** (Variante B, nicht globaler Zaehler C).
3. **Init = Copy** der Vorlage als Uebersetzungs-Startpunkt (nicht leerer Draft).
4. **Offenes Sprach-Set, KEIN CHECK** — DB-seitig frei; Validierung in der
   Anwendungs-Schicht. Weitere Sprachen brauchen keine Migration.
