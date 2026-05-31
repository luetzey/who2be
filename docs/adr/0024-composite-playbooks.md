# ADR-0024 — Composite-Playbooks / Orchestrierungs-Relation

- Status: Akzeptiert
- Datum: 2026-05-31
- Kontext: Who2Be Phase 4 — Composite-Playbooks (Plan 2026-05-31, Gap 2.1)

## Kontext

Notion-Agent-Room modelliert `Type = Atomic | Composite` und eine Self-Relation
`Composes` / `Composed By`: ein Composite-Playbook orchestriert Atomics in
einer Sequenz. who2be-Playbooks sind flach (nur Playbook→Resource-Refs ohne
Orchestrierungs-Achse). Die Gap-Analyse 2026-05-31 identifiziert dieses Fehlen
als strukturellen Block fuer komplexe Agenten-Workflows.

Anforderungen (vom User gesperrte Design-Entscheidungen):

1. **Beliebige Tiefe** mit Zyklus-Schutz — keine Single-Level-Beschraenkung.
2. **Composite-Sein abgeleitet**, nicht explizit: Playbook hat Kinder → es ist
   Composite. Kein redundantes `kind`-Feld.
3. Sub-Playbooks werden im MCP als geordnete Liste mitgeliefert (kein
   On-Demand-Vertrag wie Notion — who2be loest serverseitig auf).

## Optionen

### A — Explizites `kind`-Feld auf `playbook`-Tabelle

`kind IN ('atomic', 'composite')`. Vorteil: direkt filterbar. Nachteil:
Redundanz — `kind` muss manuell zu den Kinder-Links konsistent gehalten werden;
Autor vergisst `kind=composite` → falsch. Verworfen.

### B — Single-Level-Restriktion (nur ein Level Kinder erlaubt)

Einfache DB-Pruefung via CHECK. Nachteil: zu starr laut User-Anforderung;
verschachtelte Workflows (z.B. Compound-Steps mit eigenen Sub-Steps) sind
praxisrelevant. Verworfen.

### C — Self-m:n-Relation `playbook_composition` mit `WITH RECURSIVE`-Zyklus-Guard (gewaehlt)

Separate Tabelle `playbook_composition (parent_id, child_id, ...)` mit Position.
Composite-Sein = `EXISTS(child)`. Zyklen verhindert der Service via
`WITH RECURSIVE` vor jedem Set-Call. Direkte Selbst-Referenz faengt ein
DB-`CHECK`-Constraint zusaetzlich ab.

## Entscheidung

**Option C.**

### Schema (`0027_playbook_composition.sql`)

```sql
CREATE TABLE playbook_composition (
    parent_id    uuid NOT NULL,
    child_id     uuid NOT NULL,
    workspace_id uuid NOT NULL,
    owner_id     uuid NOT NULL,
    position     smallint NOT NULL DEFAULT 0,
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (parent_id, child_id),
    CONSTRAINT playbook_composition_no_self CHECK (parent_id <> child_id),
    FOREIGN KEY (workspace_id, parent_id)
        REFERENCES playbook (workspace_id, id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, child_id)
        REFERENCES playbook (workspace_id, id) ON DELETE CASCADE
);
CREATE INDEX playbook_composition_child_idx
    ON playbook_composition (workspace_id, child_id);
```

Composite-FKs auf `(workspace_id, id)` erzwingen Same-Workspace-Isolation
(Defense-in-Depth, analog `0016_playbook_resource_link.sql`). `position` ordnet
die Sub-Playbooks fuer die Sequenz.

### Lese-Pfade

- `GET /{id}/composes` → geordnete Kinder-Liste (`ORDER BY position ASC`),
  JOIN auf aktive oder Current-Version je Kontext (API-Token = active_only).
- `GET /{id}/composed_by` → Eltern-Zeiger als `PlaybookRef (id, name)`.
- `PlaybookRead.is_composite` → abgeleitet via `EXISTS (SELECT 1 FROM
  playbook_composition WHERE parent_id = p.id)`.

### Schreib-Pfad (`PUT /{id}/composes`)

Set-Replace-Semantik (analog `persona_playbook`). Ablauf in einer Transaktion:

1. `SELECT ... FOR UPDATE` auf Parent-Zeile (Lock, Not-Found-Guard).
2. Kinder im Workspace pruefen.
3. **`WITH RECURSIVE`-Zyklus-Guard**: Nachfahren aller neuen Kinder berechnen;
   trifft Parent darin auf → 409 Conflict.
4. DELETE + INSERT mit `position = ordinality - 1`.

Direkte Selbst-Ref faengt zusaetzlich der DB-CHECK vor dem Insert.

### MCP-Vertrag

`PlaybookWithResources.composed_playbooks: list[PlaybookRead]` — genau eine
Ebene aktiver Kinder, geordnet nach `position`. Tiefere Ebenen via erneutem
`fetch_playbook(child_id)` nachladen. Payload bleibt dadurch beschraenkt;
ein Composite-Agent folgt der Sequenz Schritt fuer Schritt.

### Versionierung

Bewusst Out of Scope: die Composition-Relation ist eine Aktuell-Stand-Relation
(analog `persona_playbook`, ADR-0004). Historisierte Composition (welche Kinder
hatte der Composite zu Zeitpunkt X?) ist ein eigener Block und nicht noetig
fuer Phase 4.

## Konsequenzen

- `PlaybookRead` erhaelt `is_composite: bool = False` (additive, Backward-Compat).
- API-Kontrakt additiv: existierende Clients sehen das neue Feld, brechen nicht.
- Same-Workspace-Isolation ist DB-erzwungen (Composite-FKs) und Service-geprueft
  (Workspace-Check vor Insert).
- Zyklus-Guard liegt im Service (`WITH RECURSIVE`) — der CHECK deckt nur den
  trivialen Selbst-Referenz-Fall direkt in der DB.
- Migration `0027` ist idempotent (`CREATE TABLE IF NOT EXISTS`,
  `CREATE INDEX IF NOT EXISTS`).
