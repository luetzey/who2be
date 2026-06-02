# Agent-Invocation-Achsen

Zwei orthogonale Wege, wie ein Agent ein Playbook zur Laufzeit nutzt.

## Applied vs. Triggered

| Achse | Mechanik | Laufzeit-Verhalten |
|---|---|---|
| **Applied** (immer geladen) | `{{playbook}}`-Pill im System-Prompt-Template | Der Resolver bettet die aktive Version bei jedem `fetch_agent`-Aufruf fix ein — kein Trigger noetig, kein MCP-Call. |
| **Triggered** (on-demand) | `persona_playbook`-Link + denormalisiertes `triggers`-Feld | Der Agent ruft `list_triggers()` → Trigger-Match → `fetch_playbook(id)` nur wenn ein Keyword auftaucht. |

**Wichtig:** Applied-Playbooks fuehren typischerweise kein `triggers`-Feld und
erscheinen deshalb nicht in der `list_triggers`-Discovery-Liste (Test: `test_list_triggers_excludes_triggerless_playbook`). Die Trennung ist damit sauber — kein doppeltes Laden.

## Composite-aware Pill (B1)

Zeigt eine Applied-Pill auf ein **Composite-Playbook** (hat Kinder in
`playbook_composition`), rendert der `PlaybookResolver` automatisch die
Orchestrierungs-Sequenz:

1. Composite-Body zuerst.
2. `## Ablauf (Sub-Playbooks)` — nummerierte Liste der aktiven Kinder, geordnet
   nach `position`. Inaktive oder geloeschte Kinder werden uebersprungen.

Atomic-Pills bleiben unveraendert (nur eigener Body).

## Agenten-Reise

Vollstaendige Akzeptanz-Checkliste: Jeder Schritt muss mit den vorhandenen
MCP-Tools und dem Default-Template-Seed lueckenlos durchfuehrbar sein.

### 1. Boot

`fetch_agent(agent_id)` → gerenderter System-Prompt.

Der gerenderte Prompt enthaelt (E4-Checkliste):
- **Persona-Profil:** `{{ persona profile }}` expandiert zu Beschreibung +
  BlockNote-Body + Modi-Sektion (falls Modi vorhanden).
- **Applied Playbooks:** vom Operator per Pill eingebettet — already expanded,
  kein MCP-Call noetig.
- **Tools-Uebersicht:** `{{ tools-overview }}` → Werkzeug-Katalog mit
  Composite-/Modi-/Applied-Hinweisen.
- **Datum:** `{{ date }}` → aktuelles Datum (ISO oder „human").

#### Briefing-Pills (ADR-0025)

Drei zusaetzliche Pills briefen den Agenten **handlungsorientiert** — der Fokus
liegt darauf, dass der Agent nach dem Lesen weiss, *welches* Tool er *wann*
ruft:

- **`persona-ref` (Persona als MCP-Handle):** Rendert keine Inhalte, sondern
  die Anweisung „Deine Persona ist **NAME** (id: …). Lade sie via
  `get_persona("<id>")` …". So holt sich der Agent Profil + Modi dynamisch
  zur Laufzeit, statt einen Snapshot fest im Prompt zu tragen. Alternative zum
  einbettenden `persona-field:profile`.
- **`persona-field:modes`:** Bettet nur die `## Modi`-Sektion ein (Teilmenge
  von `profile`); ohne Modi bleibt die Stelle leer.
- **`playbooks-catalog` (Playbook-Briefing-Tabelle):** Markdown-Tabelle der
  persona-verknuepften aktiven Playbooks — **Playbook | Trigger | Aufruf |
  Beschreibung**. Die `Aufruf`-Spalte enthaelt den konkreten
  `fetch_playbook("<id>")`-Call. Pill-Setting `target_id ∈ {all, triggered}`
  steuert, ob nur Playbooks mit Trigger gelistet werden. So ist der Agent
  vorab gebrieft, was er wann laden kann — ohne erst `list_triggers()` zu
  rufen.

### 2. Persona / Modi

`get_persona(identifier)` gibt `PersonaRead.content.modes` zurueck.

- Modi vorhanden: Trigger-Liste pruefen, passenden Modus waehlen;
  `identity_add` + `output_style_override` anwenden.
- Kein Trigger-Match: Default-Modus (Mode mit `is_default=true`) nutzen.
- Keine Modi: Persona-Persoenlichkeit direkt aus dem Profil-Block.

### 3. Playbook / Composite

`list_triggers()` → Trigger-Match → `fetch_playbook(playbook_id)`.

- Atomares Playbook: Body lesen, Schritte ausfuehren.
- Composite-Playbook (`composed_playbooks` nicht leer): der gerenderte Body
  enthaelt bereits eine nummerierte `## Ablauf (Sub-Playbooks)`-Sequenz;
  der Agent folgt ihr der Reihe nach. Einzelne Kinder koennen via
  erneutem `fetch_playbook(child_id)` vertieft werden (eine Ebene inline,
  tiefere rekursiv nachladbar).

### 4. Resource / Wissen

- Ueber Playbook-Resource-Refs (bereits in `fetch_playbook`-Antwort).
- Gezielt: `list_resources(tag?)` → gefilterte Knowledge-Base →
  `fetch_resource(resource_id)`.

### Zusammenfassung als Tabelle

| Schritt | Tool | Was der Agent tut |
|---|---|---|
| Boot | `fetch_agent` | Prompt mit Profil + applied Pills + Tools-Overview + Datum lesen |
| Persona | `get_persona` | Persoenlichkeit + Modi laden, Modus waehlen |
| Trigger-Erkennung | `list_triggers` | Keyword-Match → Playbook-ID |
| Playbook | `fetch_playbook` | Body lesen; bei Composite: Sequenz abarbeiten |
| Wissen | `list_resources` / `fetch_resource` | Tag-Filter + gezielter Body-Fetch |

Verweis: ADR-0024 (Composite-Playbooks), Plan `2026-05-31-1630_composite-applied-modi.md`
Tracks A–E. Default-Template-Seed: `workspace_repository.py::_DEFAULT_TEMPLATES`
(Laufzeit) und `migrations/0023b_seed_default_templates.sql` (DB-Migrations-Lauf).
