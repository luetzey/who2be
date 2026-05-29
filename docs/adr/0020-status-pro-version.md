# ADR-0020 — Status-Workflow pro Version (Draft/Review/Active/Inactive)

- Status: Akzeptiert
- Datum: 2026-05-28
- Kontext: Who2Be Phase 2.1b — Status-Workflow + Dashboard

## Kontext

Heute sind Persona- und Playbook-Versionen anonyme Snapshots: jede neue
Version wird `current_version` und ist sofort "live" gegenueber dem
MCP-Server (`fetch_playbook`, `get_persona`). Es gibt kein Konzept fuer
"in Arbeit" oder "in Review". Mit dem Tenant-Layer aus ADR-0019 und dem
Reviewer-Flow aus dem Phase-2-Plan brauchen wir:

- **Editieren ohne Live-Mutation:** PUT auf eine Active-Persona darf
  die aktive Version nicht ueberschreiben.
- **Sichtbare Zwischenzustaende:** ein Editor sieht "ich arbeite an
  Draft v4 waehrend v3 live ist".
- **Reviewer-Promotion:** in Phase 2.3 setzt ein Admin den Status auf
  `active`; bis dahin macht das der Owner selbst, aber der Pfad ist
  schon derselbe.
- **Deterministisches MCP:** `fetch_playbook` muss exakt eine Version
  pro Entity zurueckgeben — nicht "latest", sondern "active".
- **Append-only Audit:** wer hat wann was promotet?

Plan-Vorlage: `.claude/plan/2026-05-27-1921_phase-2-vollwertige-app.md`,
§2.1.A/C/E. Migrations (Schema-Anteil) sind in Phase 2.1a-1 schon
gemerged (`0011_status_on_versions.sql`, `0012_status_history.sql`).
Diese ADR fasst die State-Machine fest, die zugehoerige Code-Umsetzung
folgt in Phase 2.1b-1 (Endpoints).

## Optionen

- **A — Status auf Aggregat-Zeile.** `persona.status` /
  `playbook.status`. Eine Spalte, einfache Queries, aber keine
  History je Version und keine parallelen Zustaende ("v3 active, v4
  draft").
- **B — Status pro Version + DB-erzwungene Invariante (gewaehlt).**
  `status` auf `persona_version` und `playbook_version` mit `CHECK`-
  Constraint; Partial Unique Indices pro Status-Slot erzwingen
  Eindeutigkeit (`max. 1 Draft / 1 Review / 1 Active je Entity`).
  Status-Wechsel landet in `status_history`-Audit-Tabelle.
- **C — Kein Status, Versionen anonym.** Status quo. Bricht den
  Reviewer-Flow und macht das Editieren live-aktiver Personas
  destruktiv.

## Entscheidung

**Option B.**

**State-Machine** lebt in
`packages/models/src/who2be_models/status.py` (`VersionStatus` StrEnum +
`ALLOWED_TRANSITIONS`):

- `draft → {review, inactive}`
- `review → {draft, active, inactive}`
- `active → {inactive}`
- `inactive` ist terminal

`review → draft` ist Absicht: ein Reviewer kann den Autor zurueck an
den Tisch schicken, ohne den Inhalt zu verwerfen. `inactive` als
Terminal-Zustand passt zum Migration-Backfill aus
`0011_status_on_versions.sql`, der alle Nicht-`current_version`-Eintraege
auf `inactive` setzt — daraus soll nichts "wiederbelebt" werden, neue
Drafts bekommen eine neue Versions-Nummer.

**Default-Status fuer neue Versions (Update Phase 3-0, 2026-05-29).** Neue
Versions starten mit `status = 'draft'` (Migration
`0019_status_default_draft.sql`); vor Phase 3-0 war der Default `inactive`,
was die Status-Action-Bar in der UI fuer frisch angelegte v1 unsichtbar
liess (Smoke-Findings F-02 / F-13). Bestand: ein einmaliger Backfill hebt
`current_version`-Rows ohne Active- oder Draft-Schwester von `inactive` auf
`draft` — der partial-unique-index `*_draft_uniq` aus
`0011_status_on_versions.sql` bzw. `0015_resource.sql` schuetzt vor
Doppel-Drafts. Versions, die schon mit Active-Schwester leben (z. B.
inactive-historisch nach einem Promote), bleiben unangetastet.

**DB-Invariante.** Partial Unique Indices in
`0011_status_on_versions.sql`:

```sql
CREATE UNIQUE INDEX persona_version_active_uniq
    ON persona_version (persona_id) WHERE status = 'active';
CREATE UNIQUE INDEX persona_version_draft_uniq
    ON persona_version (persona_id) WHERE status = 'draft';
CREATE UNIQUE INDEX persona_version_review_uniq
    ON persona_version (persona_id) WHERE status = 'review';
```

Analog `playbook_version`. Das Anwendungs-Validate (`is_allowed_transition`)
schuetzt vor falschen Uebergaengen; der DB-Index schuetzt vor Race
Conditions ("zwei Drafts gleichzeitig").

**Edit-Verhalten** (Code in 2.1b-1):

- `PUT /v1/workspaces/{ws}/personas/{id}` mit Active-Persona:
  - neuer Row in `persona_version` mit `version = current_version + 1`,
    `status = 'draft'`,
  - `persona.current_version` bleibt unveraendert (zeigt weiter auf den
    Active-Eintrag).
- Wenn schon ein Draft existiert: `409 Conflict` mit Hinweis "Promote
  oder verwirf bestehenden Draft erst" (die DB-Unique-Constraint wuerde
  sonst sowieso werfen — wir uebersetzen sie sauber).

**Transition-Endpoint** (Code in 2.1b-1):

`POST /v1/workspaces/{ws}/personas/{id}/versions/{v}/transition`
Body `{to: "review" | "active" | "inactive", note?: string}`. Service:

1. Lade aktuelle Version + Status.
2. `is_allowed_transition(current, to)` — sonst 409.
3. UPDATE in einer Transaktion: setze neuen Status. DB-Index prueft
   Invariante.
4. Beim `active`-Switch: alte Active-Version → `inactive`,
   `persona.current_version` zieht auf die neue Active-Version nach.
5. INSERT in `status_history` (entity_type, entity_id, from_status,
   to_status, changed_by, note). Status-Wechsel bumpt **keine**
   Version — der Inhalt ist unveraendert.

**MCP-Read-Tools** filtern Server-seitig auf `status = 'active'`:
`get_persona`, `list_playbooks`, `fetch_playbook` sehen nie Drafts oder
Reviews. Damit ist das Verhalten des MCP-Servers eindeutig spezifiziert
(siehe §2.1.D).

**Dashboard-Datenquelle** (Code in 2.1b-2): KPIs `active_personas`,
`active_playbooks`, `pending_reviews` direkt aus `*_version.status` per
COUNT-Aggregat; `activity` aus `status_history` mit Index
`(entity_type, entity_id, changed_at DESC)`; Status-Verteilung pro
Entity-Typ analog ueber COUNT GROUP BY.

**Models** (Phase 2.1b-0, diese PR):

- `VersionStatus` StrEnum + `ALLOWED_TRANSITIONS` + `is_allowed_transition`.
- `StatusHistoryEntry` als Read-Modell der `status_history`-Tabelle.
- `DashboardResponse` + `DashboardKpis` + `EntityStatusDistribution` +
  `DashboardStatusDistribution`.
- `PersonaRead`/`PlaybookRead` bekommen `current_status` und
  `has_pending_draft` (Defaults `inactive` / `False`, damit existierende
  Konsumenten valide bleiben).
- `PersonaVersionRead`/`PlaybookVersionRead` bekommen `status` (Default
  `inactive` — deckt den Migration-Default).

## Konsequenzen

- API-Kontrakt aendert sich additiv: existierende Clients sehen die
  neuen Felder, aber alte Builds, die sie ignorieren, brechen nicht.
- `status_history.entity_type` enthaelt bereits `'resource'` als
  zulaessigen Wert — Phase 2.2 (Resources mit Block-Editor) erbt den
  Status-Flow ohne weitere Migration.
- Status-Wechsel ist nicht versionsbehaftet: zwei Promote-Schritte
  hintereinander erzeugen zwei `status_history`-Rows, aber keine neue
  `persona_version`. Damit ist die Versions-Historie semantisch sauber
  ("was hat sich am Inhalt geaendert") getrennt von der Status-Historie
  ("wer hat wann promotet").
- DB-Invariante schuetzt vor Bugs im Service: selbst wenn `is_allowed_transition`
  uebersehen wird, kann die DB nie zwei Active-Versionen einer Entity
  halten.
- Roll-Back ist billig: Spalten + Indices droppen, History-Tabelle
  loeschen. Status-Daten waeren weg, aber der Inhalt der Versionen ist
  unangetastet.
- Phase 2.3 (Multi-User) reicht oben drauf nur noch RBAC nach: Editor
  darf `draft → review`, Admin darf `review → active`. Die State-Machine
  selbst bleibt.
