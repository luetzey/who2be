# ADR-0009 — JSONB-Content: Strict-on-Write, Lax-on-History

- Status: Akzeptiert
- Datum: 2026-05-26
- Kontext: Who2Be MVP (PROJ-19), Plan-Review 2026-05-26

## Kontext

`persona_version.content` und `playbook_version.content` sind `jsonb`-
Spalten, getypt durch `PersonaContent` bzw. `PlaybookContent` aus
`packages/models`. Jeder Update friert einen Snapshot ein.

Spaetestens nach mehreren Schema-Iterationen (neue optionale Felder,
umbenannte Felder, deprecierte Felder) gibt es zwei widerspruechliche
Anforderungen:

- **Create/Update** sollen *strikt* validieren — falsche Tipps gehoeren
  vor der Persistenz abgefangen.
- **History-Read** soll *tolerant* sein — alte Snapshots in einem
  veralteten Schema sollen weiterhin parseable bleiben, ohne dass jede
  Schema-Aenderung eine SQL-Migration aller History-Zeilen erzwingt.

## Optionen

- **A — Strict-everywhere.** Aktuelles Schema gilt fuer Read und Write;
  Schema-Bumps erfordern Migration aller History-Snapshots. Konsistent,
  aber teuer und nicht rueckwaertskompatibel fuer alte Versions-Datensaetze
  bei Pflichtfeld-Adds.
- **B — Strict-on-Write, Lax-on-History.** Zwei Models pro Aggregat:
  `PersonaContent` (strict, fuer Create/Update) und `PersonaContentRead`
  (lax, fuer Versions-Read, mit Defaults und `extra="ignore"`). Schema-
  Bumps brauchen keine Daten-Migration; deprecated Felder werden im Read-
  Model toleriert, im Write-Model entfernt.
- **C — Versioniertes Schema im jsonb (`schema_version`-Feld).** Reader
  dispatcht ueber `schema_version` auf das passende Model. Maximale
  Flexibilitaet, aber sofortige Komplexitaet; der konkrete Nutzen tritt
  erst bei radikalen Pivots auf — YAGNI fuer das MVP.

## Entscheidung

**B — Strict-on-Write, Lax-on-History.**

- `PersonaContent` und `PlaybookContent` bleiben strict (Pydantic-
  Default: `extra="forbid"`, alle Pflichtfelder bleiben Pflicht).
- Neu: `PersonaContentRead` und `PlaybookContentRead` mit
  `model_config = ConfigDict(extra="ignore")`, alle Felder mit Default,
  deprecierte Felder duerfen einfach weggelassen werden.
- `PersonaVersionRead` / `PlaybookVersionRead` aus `packages/models`
  werden umgehaengt auf die `…ContentRead`-Variante.
- Service-Layer: `create/update` validieren mit der strict-Variante;
  `get_version` / `list_versions` parsen mit der lax-Variante.

## Konsequenzen

- Zwei Pydantic-Models pro Content-Typ — geringer Mehraufwand
  (~15 Zeilen je Aggregat), klare Trennung.
- Tests pro Aggregat decken beide Bahnen:
  - Write rejected fehlende Pflichtfelder.
  - Read toleriert Snapshot ohne Pflichtfeld und liefert Default.
- Schema-Aenderungen ohne SQL-Migration moeglich: neues Pflichtfeld im
  Write-Model wird mit Default ins Read-Model gespiegelt, History bleibt
  lesbar.
- Restore-from-Version (post-MVP) muss bewusst eine *strict*-Validierung
  durchfuehren, wenn ein History-Snapshot zurueckgesetzt wird — sonst
  schleicht ein nicht mehr akzeptables Schema in die aktuelle Zeile.
  Wird im Restore-Endpunkt explizit dokumentiert.
- ADR-0004 (Versionierung) bleibt unveraendert; diese ADR ist ein
  orthogonaler Type-Layer-Vertrag.
</content>
</invoke>