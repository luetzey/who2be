# Plan — Composite-Playbooks, Applied-via-Pill, Persona-Modi

**Datum:** 2026-05-31
**Branch:** `claude/modest-hamilton-OIyAE`
**Anlass:** Drei Funktionslücken ggü. dem Notion Agent Room schließen
(Gap-Analyse 2026-05-31). Umgesetzt werden die Gaps **2.1**
(Composite-Playbooks / Orchestrierung), **2.3** (Applied „loaded, not
triggered") und **3.4** (Multi-Modus-Personas / Modi).

## Kontext

who2be ist die produktisierte Nachfolge des Notion Agent Room. Drei
Modellierungs-Achsen aus Notion fehlen heute strukturell:

- **2.1 Composite-Playbooks:** Notion hat `Type = Atomic|Composite` + die
  Self-Relation `Composes`/`Composed By`; ein Composite orchestriert Atomics
  in einer Sequenz. who2be-Playbooks sind flach (nur Playbook→Resource-Refs).
- **2.3 Applied:** Notion-Checkbox „geladen, nicht getriggert". who2be kennt
  nur den Trigger-/Discovery-Pfad.
- **3.4 Modi:** Notion-Persona-Body-Sektion `## Modi` (Multi-Modus-Agents).
  who2be-Persona kann das nur als Freitext-BlockNote halten, ohne Struktur.

## Gesperrte Design-Entscheidungen (User, 2026-05-31)

1. **2.1 Verschachtelung:** Beliebige Tiefe **mit Zyklus-Schutz**
   (`WITH RECURSIVE`-Guard), nicht nur eine Ebene.
2. **2.3 Mechanik:** **Nur Pill/Slash** — kein DB-Flag. Der bestehende
   Welle-5-`{{playbook}}`-Placeholder ist bereits „immer geladen". Wir bauen
   die Pill-Mechanik aus (Composite-aware) + dokumentieren die Achse, statt
   eine `applied`-Spalte einzuführen.
3. **Bootstrap-Wiring:** Ja, im selben Plan — Default-Templates + Renderer +
   BASE-Klauseln so erweitern, dass die neuen Achsen zur Laufzeit wirken.

## Bestehende Konventionen (verifiziert)

- Versionierung: Identity-Tabelle + `*_version`-Tabelle, Status pro Version,
  denormalisierte Filterspalten auf der Identity-Zeile (ADR-0004, 0020).
- m:n-Links: eigene Tabelle mit Composite-FK auf `(workspace_id, id)` beider
  Seiten (Defense-in-Depth), `owner_id` als Audit, `position` für Ordnung —
  siehe `0016_playbook_resource_link.sql`.
- Link-Stack: Router (`/playbooks`-Prefix) → Service (`require_role(editor)`,
  Dedupe, Set-Replace) → Repo (atomare Transaktion, `FOR UPDATE` auf
  Parent-Zeile) — siehe `persona_playbooks.py` / `persona_playbook_service.py`
  / `persona_playbook_repository.py`.
- jsonb-Content darf additiv evolvieren ohne Migration (ADR-0009).
- Welle-5-Placeholder: Backend `services/placeholders/{registry,renderer}.py`
  mit Resolver-Protokoll + REGISTRY-Dict; 5 Kinds (`playbook`, `resource`,
  `persona-field`, `date`, `tools-overview`). Web
  `components/editor/system-prompt/` (SystemPromptEditor, PlaceholderBlock,
  slashMenu.ts, pickers/). `system_prompt_template.body_format ∈ {plain,
  blocknote}`. MCP `fetch_agent` rendert serverseitig.
- Nächste freie Migrationsnummer: **0027**. Nächste ADR: **0024**.

---

# Track A — Composite-Playbooks (Gap 2.1)

**Kernidee:** Composite-Sein wird **abgeleitet** (Playbook hat Kinder →
Composite), kein redundantes Typ-Feld. `playbook.type` bleibt die *semantische*
Achse (prompt/instructions/…); die Orchestrierungs-Achse ist orthogonal — genau
wie in Notion `Type` (Atomic/Composite) orthogonal zu `Tags` (thematisch) ist.

### A1 — ADR-0024 (Composite-Playbooks / Orchestrierung)

`docs/adr/0024-composite-playbooks.md`. Entscheidung: Self-m:n-Relation
`playbook_composition` mit `position`; Composite-Sein abgeleitet; beliebige
Tiefe mit `WITH RECURSIVE`-Zyklus-Schutz; Sub-Playbooks werden im MCP als
geordnete Liste mitgeliefert (kein „on-demand"-Vertrag wie Notion, da who2be
serverseitig auflöst). Verworfen: explizites `kind`-Feld (Redundanz),
Single-Level-Restriktion (zu starr laut User).

### A2 — Migration `0027_playbook_composition.sql`

```sql
-- Migration 0027 — playbook_composition (Gap 2.1, ADR-0024)
-- Self-m:n: parent (Composite) -> child (Sub-Playbook), geordnet via position.
-- Composite-FKs auf (workspace_id, id) erzwingen Same-Workspace (wie 0016).
-- CHECK verhindert direkte Selbst-Referenz; transitive Zyklen prüft der
-- Service via WITH RECURSIVE vor dem Insert.
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

### A3 — Models

`packages/models/src/who2be_models/links.py`:
```python
class PlaybookCompositionLinkSet(BaseModel):
    """Eingabe für PUT /playbooks/{id}/composes — geordnete Set-Replace.
    Reihenfolge der Liste = position (0..n). Leere Liste löst alle Kinder."""

    model_config = ConfigDict(extra="forbid")
    child_ids: list[UUID] = Field(default_factory=list, max_length=200)
```

`packages/models/src/who2be_models/playbook.py` — `PlaybookRead` ergänzen:
```python
    is_composite: bool = False  # abgeleitet: EXISTS child in playbook_composition
```
(Default `False`, damit alte Validierungs-Pfade ohne die Spalte weiter gültig
sind.) `PlaybookRef` (id+name) wird für Kinder & Eltern wiederverwendet.

### A4 — Repository `PgPlaybookCompositionRepository`

Neue Datei `apps/api/src/who2be_api/repositories/playbook_composition_repository.py`
analog zu `persona_playbook_repository.py`:
- `parent_belongs_to(workspace_id, parent_id) -> bool`
- `list_children(parent_id, active_only=False) -> list[PlaybookRead]` —
  JOIN `playbook_composition pc` → `playbook p` → Version-Join (current bzw.
  `status='active'` bei `active_only`), `ORDER BY pc.position ASC`. Selektiert
  dieselben Spalten wie `_SELECT_CURRENT`/`_SELECT_ACTIVE` **plus** das
  abgeleitete `is_composite`:
  ```sql
  EXISTS (SELECT 1 FROM playbook_composition c WHERE c.parent_id = p.id)
        AS is_composite
  ```
- `list_parents(child_id) -> list[PlaybookRef]` (Reverse „Composed By").
- `set_composition(workspace_id, owner_id, parent_id, child_ids) -> SetLinksResult`
  in **einer** Transaktion:
  1. `SELECT 1 FROM playbook WHERE id=$parent AND workspace_id=$ws FOR UPDATE`
     (Parent-Lock; nicht gefunden → `parent_found=False`).
  2. Kinder im Workspace prüfen (`id = ANY($child_ids)`); fehlende →
     `missing_child_ids`.
  3. **Zyklus-Guard** (nur wenn child_ids nicht leer):
     ```sql
     WITH RECURSIVE descendants(id) AS (
         SELECT child_id FROM playbook_composition
           WHERE parent_id = ANY($child_ids::uuid[])
         UNION
         SELECT pc.child_id FROM playbook_composition pc
           JOIN descendants d ON pc.parent_id = d.id
     )
     SELECT 1 FROM descendants WHERE id = $parent_id;
     ```
     Trifft → `cycle=True` (Parent ist Nachfahre eines neuen Kindes →
     Zyklus). Direkte Selbst-Referenz fängt zusätzlich der CHECK.
  4. `DELETE FROM playbook_composition WHERE parent_id=$1`, dann Insert mit
     `position = ordinality-1`:
     ```sql
     INSERT INTO playbook_composition
        (parent_id, child_id, workspace_id, owner_id, position)
     SELECT $1, c.id, $3, $4, c.ord - 1
       FROM unnest($2::uuid[]) WITH ORDINALITY AS c(id, ord);
     ```

`SetLinksResult` um `parent_found`, `missing_child_ids`, `cycle: bool`
erweitern (eigenes Dataclass im neuen Repo, Muster wie `persona_playbook`).

### A5 — Service `PlaybookCompositionService`

`apps/api/src/who2be_api/services/playbook_composition_service.py` analog
`PersonaPlaybookService`:
- `list_children(ctx, parent_id)` / `list_parents(ctx, parent_id)` — 404 wenn
  Parent nicht im Workspace; `active_only=ctx.is_api_token`.
- `set_composition(ctx, parent_id, data)` — `require_role(editor)`,
  reihenfolge-erhaltend dedupen (`dict.fromkeys`), Parent-Selbst-ID aus der
  Liste filtern (defensiv), Repo aufrufen. Mapping:
  - `parent_found=False` → 404
  - `missing_child_ids` → 404 („mind. ein Sub-Playbook existiert nicht / fremder
    Workspace")
  - `cycle=True` → **409 Conflict** („Verknüpfung würde einen Zyklus erzeugen")

### A6 — Router `playbook_composition.py`

Eigene Datei (Prefix `/playbooks`, gemountet unter
`/v1/workspaces/{workspace_id}`), wie `persona_playbooks.py`. In
`app.py`/Router-Registry mounten.
- `GET  /{playbook_id}/composes`     → `list[PlaybookRead]` (geordnet)
- `PUT  /{playbook_id}/composes`     → `list[PlaybookRead]` (Set-Replace)
- `GET  /{playbook_id}/composed_by`  → `list[PlaybookRef]` (Reverse)

### A7 — MCP

`apps/mcp/src/who2be_mcp/server.py` — `PlaybookWithResources` erweitern:
```python
    composed_playbooks: list[PlaybookRead] = []  # geordnete, aktive Kinder
```
`fetch_playbook` lädt zusätzlich `client.get_playbook_composes(parsed)`
(neuer Client-Call gegen `GET /{id}/composes?…` mit `active_only`-Semantik
über den Token-Pfad) und füllt das Feld. Docstring: bei einem Composite folgt
der Agent der Reihenfolge in `composed_playbooks`; Resource-Refs der Kinder
werden bei Bedarf via `fetch_playbook(child_id)` nachgeladen (Payload bleibt
beschränkt — nur eine Ebene Kinder inline).

`apps/mcp/.../client.py`: Methode `get_playbook_composes(playbook_id)`.

### A8 — Web

`apps/web/src/features/playbooks/components/`:
- **`PlaybookComposesPicker.tsx`** — geordneter Multi-Select (Muster:
  `ResourceBlockLinkPicker` + `PlaybookLinkItem`), mit Up/Down-Reorder, listet
  Workspace-Playbooks außer dem aktuellen. Schreibt via
  `PUT /{id}/composes`.
- **`ComposedByList.tsx`** — read-only Backlinks (Muster `LinkedBlocksList`),
  speist sich aus `GET /{id}/composed_by`.
- `PlaybookEditorForm.tsx`: Sektion „Composes (Sub-Playbooks)" einhängen.
- Detail-Page: Badge „Composite" wenn `is_composite`, plus „Composed by".
- API-Client-Hooks unter `features/playbooks/lib` (bestehendes Muster).

### A9 — Tests (Track A)

- Repo: set/list/reorder, Same-Workspace-Guard, Selbst-Ref (CHECK), transitiver
  Zyklus (A→B→C→A), `active_only`-Schwenk, `is_composite`-Ableitung.
- Service: role-gate (viewer→403), 404 (Parent/Kind), 409 (cycle), Dedupe/Order.
- Router: GET/PUT/GET-composed_by Happy-Path + Fehlercodes.
- MCP: `fetch_playbook` liefert `composed_playbooks` geordnet & aktiv.
- Web: Picker add/remove/reorder, Composite-Badge, Composed-by-Liste
  (BlockNote-Mock-Muster wie `PlaybookDetailPage.test.tsx`).

---

# Track B — Applied „loaded, not triggered" via Pill (Gap 2.3)

**Kein DB-Flag, keine Migration.** Der Welle-5-`{{playbook}}`-Placeholder
inlinet bereits eine **spezifische** aktive Playbook-Version in den gerenderten
System-Prompt → das *ist* „immer geladen". Die Achse wird so realisiert:

| Achse | Mechanik in who2be |
|---|---|
| **Applied** (loaded) | `{{playbook}}`-Pill im System-Prompt-Template → fix eingebettet |
| **Triggered** | per `persona_playbook` verknüpft, via `list_triggers`/`fetch_playbook` on-demand |

### B1 — PlaybookResolver Composite-aware machen

`services/placeholders/registry.py` — `PlaybookResolver.resolve`: Zeigt die Pill
auf ein **Composite** (Kinder vorhanden), rendert der Resolver die
Orchestrierungs-Sequenz: Composite-Body + nummerierte Liste der aktiven Kinder
(`name` + `body`), geordnet nach `position`. So wirkt Track A direkt über die
Pill zur Laufzeit. Atomic-Pill bleibt unverändert (nur eigener Body). Lookup über
denselben `playbook_composition`-JOIN wie A4; nicht gefundene Kinder werden
übersprungen (kein Hard-Fail).

### B2 — Slash-/Pill-UX-Politur

`components/editor/system-prompt/slashMenu.ts`: Subtext des Playbook-Items
schärfen („Bettet ein Playbook **fest** ein — immer geladen, nicht
getriggert"). Optional zweites Alias `standard`. `PlaceholderBlock.tsx`: bei
Composite-Ziel ein abweichendes Pill-Icon/Label („Composite: …"). Keine neuen
Kinds nötig.

### B3 — `list_triggers` sauber halten

Verifizieren/dokumentieren: applied (= nur via Pill eingebettete) Playbooks
führen typischerweise keine `triggers` und tauchen damit ohnehin nicht in
`list_triggers` auf. Kein Code nötig, aber Test, der bestätigt, dass ein
Playbook ohne `triggers` nicht in der Discovery-Liste erscheint.

### B4 — Doku

`docs/` (z.B. `docs/agent-config.md` oder Abschnitt in `architecture.md`):
Die zwei Invocation-Wege erklären (Pill=applied vs. persona-link=triggered),
inkl. ADR-010-Mapping aus dem Notion-Vault. Kurzer ADR-Hinweis (kein eigener
ADR nötig, da reine Konventions-/Doku-Entscheidung — als Notiz in ADR-0021
oder neue `docs/decisions`-Notiz).

### B5 — Tests (Track B)

- `test_placeholder_renderer.py`: Playbook-Pill auf Composite → Output enthält
  Sequenz + Kinder-Bodies in Reihenfolge; auf Atomic → nur eigener Body;
  fehlende Kinder werden ausgelassen.
- `test_*triggers*`: triggerloses Playbook nicht in `list_triggers`.

---

# Track C — Persona-Modi (Gap 3.4)

**Struktur in `PersonaVersionContent` (jsonb) — keine Migration** (ADR-0009,
additive jsonb-Evolution). Modi sind damit automatisch versioniert.

### C1 — Models

`packages/models/src/who2be_models/persona.py`:
```python
class PersonaMode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    trigger: str | None = Field(
        default=None, max_length=2_000
    )  # kommagetrennt; leer/None = Default-Modus
    is_default: bool = False
    identity_add: str = Field(default="", max_length=5_000)  # was dieser Modus zur Identity ergänzt
    output_style_override: str = Field(default="", max_length=5_000)  # wie sich der Output ändert
```
`PersonaVersionContent` ergänzen:
```python
    modes: list[PersonaMode] = Field(default_factory=list, max_length=20)
```
`model_validator(mode="after")`: höchstens ein `is_default=True`; Modus-Namen
case-insensitive eindeutig. Verstoß → `ValueError` (→ 422).

Backward-Compat: Default `[]`; alte Clients senden das Feld nicht. `extra=
"forbid"` bleibt — additive Felder sind erlaubt, weil das Schema mit-evolviert.

### C2 — Keine neuen Endpunkte

Modi fließen durch bestehendes Persona-CRUD (`PersonaCreate`/`Update`/
`PATCH …/draft`), da Teil von `content`. `PersonaRead` liefert sie automatisch.
Promote-Validation (draft→review/active) bleibt unverändert (Modi optional).

### C3 — MCP

`get_persona` liefert `PersonaRead.content.modes` ohne Codeänderung. Docstring
ergänzen: „enthält ggf. `content.modes` (Multi-Modus-Personas)". Optionaler
Folge-Schritt (Out of Scope, s.u.): `persona-modes`-Placeholder-Kind.

### C4 — Renderer: Modi in den Prompt

Die `## Modi`-Sektion wird Teil der **neuen Persona-Profil-Expansion** (Track
E1, `persona-field`-Target `profile`): existieren `modes`, hängt die
Profil-Expansion eine `## Modi`-Sektion an (pro Modus: Name, Trigger,
Identity-Add, Output-Override). Kein neuer Placeholder-Kind. **Abhängigkeit:**
C4 setzt E1 voraus — ohne Profil-Pill gibt es kein Render-Ziel für die Modi
(die bisherige `persona-field`-Pill kann nur `name`/`description`).

### C5 — Web

`apps/web/src/features/personas/components/`:
- **`PersonaModesEditor.tsx`** — `useFieldArray` (react-hook-form), Liste
  add/remove; pro Modus: Name (`Input`), Trigger (`Input`), Default
  (`RadioGroup`/`Switch`, exklusiv), Identity-Add + Output-Override
  (`Textarea`). Alles über `@/components/ui/*` (Lint-Gate). Default-Exklusivität
  clientseitig spiegeln (nur ein Radio aktiv).
- `PersonaEditorForm.tsx`: Sektion „Modi (optional)" einhängen; bindet an
  `content.modes`.
- Detail-Page: Modi-Liste read-only rendern (Badge „Default" beim Default-Modus).

### C6 — Tests (Track C)

- Models: Validator (zwei Defaults → Fehler; doppelter Name → Fehler; leere
  modes ok). Persona-Round-Trip mit Modi (Create→Read→Update bewahrt modes).
- Renderer: Persona mit Modi → `## Modi`-Sektion im Output.
- Web: Modi add/remove, Default-Exklusivität, Submit-Payload enthält `modes`.

---

# Track D — Bootstrap-/Template-Wiring (gemeinsam)

Damit die Achsen zur Laufzeit greifen.

### D1 — Default-Templates (neue Workspaces)

`0023b`-Seed ist idempotent (`ON CONFLICT DO NOTHING`) → Edit wirkt nur für
**künftige** Workspaces. Seed-Body der drei Default-Templates um BASE-Klauseln
ergänzen (im Migrations-Text `0023b` aktualisieren **und** Klausel-Block neu
formulieren), die dem Agenten sagen:
- **Modi:** „Wenn die Persona Modi führt, wähle anhand des Modus-Triggers den
  passenden Modus; wende dessen Identity-Add + Output-Override an; ohne Match
  gilt der Default-Modus."
- **Composite:** „Ist ein eingebettetes Playbook ein Composite, folge der
  nummerierten Sequenz seiner Sub-Playbooks der Reihe nach."
- **Applied/Triggered:** „Fest eingebettete Playbooks (Pill) gelten immer;
  weitere via `list_triggers` nur bei Trigger-Match laden."

### D2 — Bestehende Workspaces (Propagation)

Bekannte Grenze (ironischerweise Notions Drift-Problem): bestehende
geseedete Templates ziehen nicht automatisch nach. Optionale Migration
`0028_update_default_template_bootstrap.sql`, die **nur unveränderte**
Default-Versionen aktualisiert (Body == alter Seed-Body → neue Body-Version
oder In-Place-Update der aktiven Version; defensiv via `WHERE body = <alt>`).
Vom User editierte Templates bleiben unangetastet. Entscheidung im Plan-Bericht
dokumentieren; falls riskant → als manueller Schritt auslagern.

### D3 — Doku

`docs/agent-config.md` (oder bestehende Architektur-Doku): die drei Achsen +
das Notion→who2be-Mapping zentral dokumentieren; Verweis aus CLAUDE.md
„Aktueller Stand".

---

# Track E — Agenten-Laufzeitsicht: Lücken schließen (Perspektivwechsel)

**Leitfrage:** Der Agent bekommt nur den gerenderten System-Prompt
(`fetch_agent`). Ab da muss er sauber von **Persona → Playbook → Resource**
durchschalten können — Persönlichkeit & Handlungsweise aus der Persona,
konkrete Abläufe aus Playbooks, Wissen aus Resources. Der Durchstich deckt
vier Lücken auf, die die Tracks A–D **nicht** automatisch schließen.

## Soll-Reise des Agenten

1. **Boot:** `fetch_agent(agent_id)` → System-Prompt mit expandierten Pills.
   Muss enthalten: Persona-Persönlichkeit, fest eingebettete (applied)
   Playbooks, Werkzeug-Übersicht, Datum.
2. **Persona verinnerlichen:** ggf. `get_persona()` für volles Profil + Modi.
3. **Prozess erkennen:** `list_triggers()` → Trigger-Match → `fetch_playbook()`
   (inkl. Composite-Sequenz) den Schritten folgen.
4. **Wissen nachschlagen:** über Playbook-Resource-Refs **oder** gezielt
   `list_resources()` → `fetch_resource()`.

## E1 — Persona-Profil-Pill (die fehlende Schlüssel-Pill) · *blockierend für C4*

**Ist:** `PersonaFieldResolver` rendert nur `name`/`description`. Die
eigentliche Persönlichkeit (Rolle, Tonfall, Beispiele) lebt in
`PersonaContent.blocks` (BlockNote) und ist **durch keine Pill** in den
System-Prompt holbar. Damit lässt sich „mit der Persona die Persönlichkeit
festlegen" heute nur erreichen, indem der Autor den Text direkt ins Template
kopiert (Drift!) oder der Agent zur Laufzeit `get_persona` ruft.

**Soll:** `PersonaFieldResolver` um Target **`profile`** erweitern:
- Rendert `description` + den Persona-Body (`content.blocks`) via vorhandenem
  `_block_plain_text`-Helper (gleiche Mechanik wie Playbook-/Resource-Body).
- Hängt — falls vorhanden — die `## Modi`-Sektion an (Track C4).
- Optional `traits` als kompakte Liste (deprecated, aber noch lesbar).
- `name`/`description` bleiben als eigene Targets erhalten (Backward-Compat).

**Web:** `PersonaFieldPicker.tsx` um die Option „Profil (vollständig)" ergänzen
(neben Name/Beschreibung). `slashMenu.ts`-Subtext schärfen.

**Tests:** Resolver `profile` rendert Body+Description+Modi; leeres Profil →
nur Description; unbekanntes Target → leerer String (Bestandsverhalten).

## E2 — `tools-overview` lehrt die neuen Achsen

**Ist:** Die kuratierte `_TOOLS`-Liste erklärt die Read-Tools, aber **nicht**,
dass (a) ein Playbook ein **Composite** sein kann (Sub-Playbooks der Reihe nach
abarbeiten), (b) die Persona **Modi** haben kann (per Trigger umschalten),
(c) fest eingebettete (Pill-)Playbooks immer gelten vs. getriggerte on-demand.

**Soll:** `_TOOLS`/Overview-Text erweitern:
- `fetch_playbook`-Eintrag: Hinweis auf `composed_playbooks` (Sequenz folgen).
- `get_persona`-Eintrag: Hinweis auf `content.modes` (Modus-Wahl per Trigger).
- Kurzer Rahmen-Absatz „applied (immer geladen) vs. triggered (bei Match)".
Deckt sich inhaltlich mit den BASE-Klauseln (Track D1) — **eine** Quelle pflegen
(Overview-Text referenziert die Achsen, Default-Template nur knapp).

**Tests:** Renderer-Snapshot der Overview enthält Composite-/Modi-/Applied-Hinweise.

## E3 — Resource-Discoverability (Tags + Filter) · *kleiner Track, keine Migration*

**Ist:** `list_resources()` liefert **alle** aktiven Resources ungefiltert;
Resources haben **keine Tags**. Playbooks haben `list_playbooks(tag, trigger)`,
Resources nichts Vergleichbares. „Wissen nachschlagen" über viele Resources
skaliert nur über Namensraten.

**Soll (analog Persona/Playbook-Tags, jsonb — keine Migration):**
- `ResourceContent` um `tags: list[TagStr] = Field(default_factory=list,
  max_length=50)` erweitern. Denormalisierte Filterspalte optional (für jetzt
  In-Query-jsonb-Filter ausreichend; Index erst bei Bedarf).
- API: `GET /resources?tag=` Filter; `ResourceSummary.tags` ergänzen.
- MCP: `list_resources(tag: str | None = None)`; `ResourceSummary` um `tags`.
- Web: TagInput im Resource-Editor (Muster Playbook-Multi-Select-TagInput);
  Tag-Anzeige/-Filter in der Resource-Liste.
- `tools-overview`: `list_resources(tag?)`-Signatur aktualisieren.

**Bewusst Out of Scope:** semantische/Volltext-Suche über Resources
(Embeddings) — das ist die „große" Knowledge-Lookup-Lösung, eigener Block.

**Tests:** Tag-Round-Trip; `list_resources?tag=` filtert; MCP-Filter; Web-TagInput.

## E4 — Bootstrap: Default-Template muss kohärent booten

**Ist:** Ob ein frischer Agent Persönlichkeit + Werkzeug-Übersicht im
System-Prompt hat, hängt allein am Seed-Template-Body (0023b) — **unverifiziert.**

**Soll:** Seed-Default-Templates so fassen (Track D1), dass der gerenderte
Boot-Prompt mindestens enthält:
1. `{{ persona profile }}`-Pill (E1) — Persönlichkeit + Modi,
2. die applied-Playbook-Pills (vom Autor gesetzt),
3. `{{ tools-overview }}`-Pill (E2) — Lookup-Wegweiser,
4. `{{ date }}`.
Verifikations-Task: aktuellen 0023b-Seed-Body lesen und gegen diese Checkliste
prüfen; fehlende Pills ergänzen.

## E5 — Doku: die drei Achsen + die Boot-Reise

In der Track-D3-Doku eine „Agenten-Reise"-Sektion ergänzen (Boot →
Persona/Modi → Playbook/Composite → Resource), inkl. der applied-vs-triggered-
Tabelle aus Track B. Dient zugleich als Akzeptanz-Checkliste.

# Reihenfolge / Agenten-Plan

Abhängigkeiten: **B hängt an A** (Composite-aware Resolver braucht die
Composition-Tabelle); **C4 hängt an E1** (Modi brauchen die Profil-Expansion als
Render-Ziel); **E4/E2 hängen an D** (Seed-Template + Overview-Text). Empfohlene
Sequenz:

1. **A (Backend):** Migration 0027, Models, Repo, Service, Router, MCP + Tests.
   Eigener Sub-Branch / Worktree (`backend-developer` Sonnet).
2. **E1 + C (Backend):** Persona-Profil-Pill (E1) zuerst, dann Modi-Model +
   Validator + Modi-in-Profil (C). Parallel zu A möglich; Renderer-Datei
   (`registry.py`) berührt A(B)/E1/C → sequenziell mergen.
3. **E3 (Backend):** Resource-Tags + `list_resources(tag?)` + Tests.
   Unabhängig, jederzeit parallel.
4. **B:** Resolver Composite-aware + Slash-Politur + Tests (nach A gemerged).
5. **Web:** PlaybookComposesPicker/ComposedByList (A), PersonaModesEditor (C),
   PersonaFieldPicker-Profil-Option (E1), Resource-TagInput (E3)
   (`frontend-developer` Sonnet), sobald Backend-JSON-Shapes fixiert.
6. **D + E2 + E4 + E5:** `tools-overview`-Text (E2), Seed-/Bootstrap-Klauseln &
   Default-Template-Verifikation (E4), Doku inkl. Agenten-Reise (E5). Zuletzt.
7. **ADR-0024** mit Track A; Doku-Notizen mit B/D/E.

Integration (Merges, Sammel-Test, Stack-Rebuild, Smoke) durch den Coder selbst.

# Definition of Done

- Python: `uv run ruff check .`, `uv run mypy .`, `uv run pytest -q` grün.
- Web: `npm run lint`, `npx tsc --noEmit`, `npm test`, `npm run build` grün.
- Migration 0027 idempotenz-geprüft (Re-Run = No-op über `pg_constraint`/
  `IF NOT EXISTS`-Muster, falls relevant).
- Security-Review der neuen DB-Pfade & Inputs via `security-reviewer`
  (Cross-Workspace-Isolation der Composition, Zyklus-Guard, jsonb-Limits).
- Conventional-Commit, Draft-PR mit Session-Link.

# Out of Scope

- Versionierte Composition-Relation (analog ADR-0004 für persona_playbook:
  bewusst Aktuell-Stand-Relation).
- `persona-modes`-Placeholder-Kind als eigener Slash-Eintrag (C4 integriert die
  Modi in die Profil-Expansion; eigener Kind später nachschiebbar).
- Modus-abhängiges Playbook-Routing (Modi sind persona-intern).
- Caching der Composite-Auflösung im Renderer (erst bei Bedarf, vgl. Welle 5).
- Batch-Backfill aller bestehenden Default-Templates ohne Unverändert-Guard.
- **Semantische/Volltext-Suche über Resources** (Embeddings) — E3 liefert nur
  Tag-Filter; echte KB-Suche ist ein eigener Block.
- Denormalisierte Resource-Tag-Filterspalte + GIN-Index (erst bei
  Performance-Bedarf; E3 nutzt zunächst jsonb-In-Query-Filter).

# Offene Punkte (im Bericht klären)

- D2: existierende-Template-Propagation automatisch (0028) vs. manuell.
- A7: Soll `composed_playbooks` im MCP rekursiv (alle Ebenen) oder nur eine
  Ebene inline sein? Default: **eine Ebene** (Payload-Schutz); tiefere via
  erneutem `fetch_playbook`.
- E1: Soll die Profil-Pill den vollen `content.blocks`-Body inline ziehen
  (Drift-Risiko vs. immer aktuell) oder nur eine Kurzfassung? Default:
  **voller Body** — die Pill rendert beim Boot stets die aktive Version,
  also kein Drift, im Gegensatz zum manuellen Kopieren ins Template.
