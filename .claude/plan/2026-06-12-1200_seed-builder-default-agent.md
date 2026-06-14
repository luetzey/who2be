# Plan — Builder als Default-„Start-Agent" nach Who2Be übersetzen

**Status:** Entwurf (wartet auf Freigabe) · **Erstellt:** 2026-06-12 · **Living document**

## 0. Ziel & Completion-Condition (`/goal`)

**Outcome:** Der Notion-Agent **„Builder"** (Agent Room) existiert als **nativer
Default-Agent** in Who2Be — automatisch mit-erzeugt bei **jeder** Workspace-
Anlage (analog zu den Default-SystemPromptTemplates), re-targeted auf das Who2Be-
Datenmodell + die MCP-Write-Tools. Er ist ein funktionsfähiger Meta-Agent
(„der Agent, der Agents baut").

**Messbare Completion-Condition (transkript-nachweisbar):**

1. `uv run pytest -q` grün — inkl. neuer Seed-Tests (Idempotenz, `activatable`,
   `fetch_agent`-Render).
2. Ein frisch erzeugter Workspace enthält nach `create()`:
   - Persona **„Builder"** (v1, `status=active`),
   - 4 Playbooks (v1, `active`) korrekt an die Persona gelinkt,
   - SystemPromptTemplate **`agent-builder`** (v1, `active`),
   - Agent **„Builder"** mit `persona_id` + `system_prompt_template_id` gesetzt,
     write-fähiger `tool_policy`, `activatable == True`.
3. `fetch_agent(<builder_id>)` rendert einen vollständigen Prompt ohne
   ungefüllte Platzhalter.
4. Bestands-Workspaces bekommen denselben Stand per Backfill-Migration `0047`.
5. `uv run ruff check .`, `uv run mypy .` grün.

**Guardrails (aus Persona/CLAUDE.md):** keine Pushes auf `main`; Entwicklung auf
`claude/gifted-rubin-5j8ow3`; kein Pattern-Drift — wir spiegeln exakt das
bestehende Seed-Muster; `security-reviewer` für die Seed-Daten + tool_policy.

---

## 1. Geklärte Architektur-Weichen

| Weiche | Entscheidung |
|---|---|
| **Lieferform** | **Produkt-Seed für alle** — Default-Agent bei jeder Workspace-Erstellung. |
| **Playbook-Treue** | **Re-Target auf Who2Be** — Inhalte beschreiben CRUD via Who2Be-MCP-Write-Tools, keine toten Notion-DB-IDs. |

---

## 2. Quelle → Ziel (Struktur-Mapping)

### Notion-Builder besteht aus
- **Persona** (`35fbe537…ac1ef085ec8ea3de`): Identity, Tone & Style, Allowed,
  Forbidden, Output Style, Cross-Agent-Routing, Skills, Notes. **Keine Modi.**
- **Systemprompt** (`35fbe537…dd226f8322b7`): Bootstrap-Loop + Agent-Spezifika
  (DB-IDs, DUAL-Relation-Disziplin, Post-Edit-Konsistenz-Check).
- **4 Playbooks**: Persona-CRUD, Playbook-CRUD, Systemprompt-CRUD, Konsistenz-Check.

### Who2Be-Zielmodell (verifiziert)
- `Agent` = `persona_id` + `system_prompt_template_id` + `tool_policy`
  (`packages/models/src/who2be_models/agent.py`); Default `status=disabled`,
  `activatable` braucht Persona+Template+**aktive** Persona-Version.
- `Persona.content` (`PersonaVersionContent`): `description`, `traits`, `tags`,
  `content` (BlockNote `PersonaContent`), `modes`, `skills`.
- `Playbook.content`: `description`, `body` (BlockNote-JSON), `type`, `tags`,
  `triggers`; M:M zur Persona via `persona_playbook`.
- `SystemPromptTemplate`: Render-Skelett mit `{{ platzhaltern }}`.
- `AgentToolPolicy` (`tool_policy.py`): `*_read` (`all|assigned|none` / bool),
  `*_write` (bool), `promote_retire` (bool).

### Mapping-Tabelle

| Notion (Builder) | Who2Be-Entität | Anmerkung |
|---|---|---|
| Persona-Property „Description" | `Persona.content.description` | Kurzfassung. |
| Identity / Tone & Style / Allowed / Forbidden / Output Style | `Persona.content.content` (BlockNote-Blocks) | Allowed/Forbidden **re-targeted** auf MCP-Tools. |
| Tone-Keywords | `Persona.content.traits` | z.B. `strukturell`, `kritisch`, `phasen-orientiert`, `trade-offs-explizit`. |
| Domänen-Schlagworte | `Persona.content.tags` | z.B. `meta-agent`, `agent-building`, `crud`. |
| (keine Modi) | `Persona.content.modes = []` | Builder ist single-mode. |
| Skills-Sektion (keine relevanten) | `Persona.content.skills` | leer / deskriptiver Hinweis. |
| Cross-Agent-Routing (OS-Architect/Inbox/…) | **entfällt** | Andere Notion-Agenten existieren in Who2Be nicht — siehe §5 offene Punkte. |
| Systemprompt Bootstrap-Loop + Agent-Spezifika | `SystemPromptTemplate agent-builder` (Body) | Bootstrap → `## Agenten-Hinweise` (Modi/Composite/Applied + `list_triggers`/`fetch_playbook`); Notion-DB-IDs & str_replace-Lessons gestrichen. |
| 4 Playbooks | 4 Who2Be-Playbooks | Re-Target, siehe §3. |

---

## 3. Re-Target der 4 Playbooks

Inhaltliche Übersetzung: „CRUD auf Notion-DBs" → „CRUD via Who2Be-MCP-Write-Tools".
`type=workflow`, je `triggers`-Stichworte, `body` als BlockNote-JSON.

| # | Notion-Playbook | Who2Be-Playbook (re-targeted) | Kern-Tools |
|---|---|---|---|
| 1 | Persona-CRUD | **Persona anlegen & pflegen** | `create_persona`, `update_persona`, `transition_persona`, `restore_persona`, `set_persona_playbooks` |
| 2 | Playbook-CRUD | **Playbook anlegen & pflegen** | `create_playbook`, `update_playbook`, `set_playbook_resource_links`, `set_playbook_composes`, `transition_playbook` |
| 3 | Systemprompt-CRUD | **Agent anlegen & pflegen** *(Re-Map)* | `create_agent`, `update_agent`, `copy_agent` (+ `tool_policy`, Persona/Template-Wiring) |
| 4 | Konsistenz-Check | **Konsistenz- & Drift-Check** | read-only: `get_persona`, `list_playbooks`, `fetch_agent` → prüft `activatable`/`missing`, aktive Version, Render |

**Re-Map-Begründung (#3):** Who2Be hat **kein** MCP-Tool für
SystemPromptTemplates (nur Seeds). Die Notion-Rolle „Systemprompt = die Daten,
aus denen ein Agent besteht" entspricht in Who2Be der **Agent-Konfiguration**
(`create_agent` verdrahtet Persona+Template+Policy). Das ist die natürlichste
1:1-Entsprechung. *Optional 5. Playbook „Resource-CRUD"* (`create_resource` …)
als Folge-Erweiterung — nicht im V1-Scope.

Die 4 Phasen des Notion-Builders (Verstehen → Vorschlag → Schreiben → Hand-Off)
bleiben als Methodik-Rahmen in der Persona/Template erhalten.

---

## 4. Seeding-Architektur (Implementierungs-Strategie)

**Bestehendes Muster** (exakt spiegeln, kein Drift):
- `apps/api/src/who2be_api/repositories/workspace_repository.py` →
  `_seed_default_templates()` läuft in **`create()`** UND
  **`ensure_personal_workspace()`**. BlockNote-Bodies als Sidecar-JSON
  (`<slug>_body.json`) neben dem Modul. Idempotenz: `ON CONFLICT … DO NOTHING`
  + Versions-Insert per `NOT EXISTS`.
- Backfill für Bestands-Workspaces: SQL-Migration (Vorbild `0023b`), `CROSS JOIN`
  über `workspace`, owner via `ws_owner`-CTE.

**Erweiterung — neue Seed-Funktion `_seed_default_agents(conn, ws_id, owner_id)`**,
aufgerufen direkt nach `_seed_default_templates()` an **beiden** Call-Sites.
Reihenfolge wegen Composite-FK (`agent → persona`, `agent → template`):

1. Template `agent-builder` (eigene Sidecar `agent_builder_body.json`,
   in `_DEFAULT_TEMPLATES`-Tuple aufnehmen → wird vom bestehenden
   `_seed_default_templates` mitgeseedet).
2. Persona „Builder": `persona` + `persona_version` (v1, `content` JSONB,
   `status=active`). Sidecar `builder_persona_content.json`.
3. 4 Playbooks: je `playbook` + `playbook_version` (v1, `active`). Sidecars
   `builder_playbook_<n>_body.json`.
4. M:M-Links `persona_playbook` (Persona ↔ 4 Playbooks).
5. `agent`-Row: `persona_id`, `system_prompt_template_id`, `tool_policy`
   (write-fähig), `status` (siehe §5).

**Status-Invarianten beachten:** Partial-unique-Index erlaubt max. 1 aktive
Version je Entität → Seed setzt **direkt** v1 auf `active` (wie Templates), kein
`transition`-Roundtrip. `status_history`-Eintrag optional (Seeds der Templates
schreiben aktuell keinen — konsistent bleiben).

**Backfill-Migration `0047_seed_builder_default_agent.sql`:** dieselbe Logik in
SQL über alle Bestands-Workspaces; idempotent; owner-CTE wie `0023b`.

**Tenancy/RLS:** Alle Inserts tragen `workspace_id` (denormalisiert, RLS seit
`0035`). Seed läuft als Owner-Identität — innerhalb der bestehenden
Workspace-Transaktion, keine RLS-Sonderbehandlung nötig.

---

## 5. Offene Entscheidungen (Empfehlung im Plan, finale Freigabe in Ausführung)

1. **Agent-Default-Status:** `enabled` vs. `disabled`.
   *Empfehlung:* **`enabled`** — die Default-Templates seeden ebenfalls direkt
   `active`; der Builder soll out-of-the-box nutzbar sein. Voraussetzung
   (`activatable`) ist durch den Seed erfüllt.
2. **`tool_policy` des Builders:** Als Meta-Agent braucht er **Writes**.
   *Empfehlung:* `persona_write`, `playbook_write`, `resource_write`,
   `agent_write` = `true`; `promote_retire` = `true`; Reads `all`. (Autorisierung
   bleibt serverseitig editor/admin — Policy ist nur die Tool-Sichtbarkeit.)
3. **Cross-Agent-Routing:** ersatzlos streichen (kein Notion-Pantheon in Who2Be)
   vs. zu generischem „bei fachfremden Themen rückfragen" eindampfen.
   *Empfehlung:* eindampfen.
4. **Owner bei Auto-Provision** (`ensure_personal_workspace`): erster Admin —
   bereits durch Signatur (`owner_id`) abgedeckt.

---

## 6. Arbeitspakete in Wellen (Orchestrierung)

> Datei-disjunkt, nach Abhängigkeit geordnet. Sub-Agent-Fan-out erst **nach**
> Freigabe dieses Plans.

**Welle 0 — Fundament (sequenziell):**
- W0.1 Notion-Bodies der 4 Builder-Playbooks fetchen (Volltext) als Roh-Input.
- W0.2 Seed-Helper-Signaturen + Sidecar-Dateinamen + tool_policy-Preset fixieren.

**Welle 1 — Content-Authoring (parallel, je 1 Sub-Agent, datei-disjunkt):**
- W1.a `builder_persona_content.json` (BlockNote) — re-targeted Persona-Body.
- W1.b `agent_builder_body.json` — Template mit Platzhaltern.
- W1.c–f je 1 Datei `builder_playbook_<1..4>_body.json` (BlockNote).

**Welle 2 — Seeding-Integration (sequenziell, hängt an Welle 1):**
- W2.1 `agent-builder` in `_DEFAULT_TEMPLATES` aufnehmen.
- W2.2 `_seed_default_agents()` schreiben + an beide Call-Sites hängen.
- W2.3 Backfill-Migration `0047` + `migrations/README` aktualisieren.

**Welle 3 — Verifikation (sequenziell):**
- W3.1 Pytest: Seed-Idempotenz (Doppel-Lauf), `activatable`, `fetch_agent`-Render,
  Persona↔Playbook-Links.
- W3.2 `ruff`/`mypy`/`pytest` grün; optional Web-Smoke (Agent erscheint in Liste).
- W3.3 `security-reviewer` über Seed-Daten + tool_policy.

---

## 7. Risiken / Fallstricke

- **Zwei Seed-Schichten synchron halten** (`workspace_repository` ↔ Migration) —
  bekannte Drift-Quelle (siehe Kommentar in `0023b`). Tests müssen **beide** Pfade
  abdecken.
- **Composite-FK-Reihenfolge** (`agent` zuletzt; Workspace-Delete entfernt Agents
  zuerst — bereits in `delete()` gehandhabt).
- **JSONB-Bind:** dict übergeben, keinen vor-serialisierten String (Codec-Falle,
  siehe Kommentar `_seed_default_templates`).
- **BlockNote-Body-Validität:** `ResourceBlock` verlangt `id`+`type` je Block —
  Sidecars müssen schema-konform sein, sonst Pydantic-Reject beim Read.
- **Locale:** Default `de` — Bodies auf Deutsch, konsistent mit bestehenden Seeds.

---

## 8. Definition of Done

- [ ] §0 Completion-Condition 1–5 erfüllt (transkript-nachweisbar).
- [ ] Seed in `create()` **und** `ensure_personal_workspace()` aktiv.
- [ ] Backfill-Migration `0047` idempotent (Doppel-Lauf ohne Duplikate).
- [ ] `ruff` / `mypy` / `pytest` grün.
- [ ] `security-reviewer`-Pass ohne offene Findings.
- [ ] Notion-Doku-Log (§ Notes des Projekts) + Pointer auf diese Plan-Datei.

---

## 9. Doku-Rückschreibung (Hybrid)

Nach Abschluss: kurzes Change-Log in die Notion-Projekt-`## Notes` mit Pointer auf
diese Datei. *(Voraussetzung: `.claude/project.json` mit echter
`notion_project_id` — derzeit nur `project.example.json` mit Platzhaltern; vor
dem Doku-Schritt klären, welche Notion-Projektseite das Ziel ist.)*

## 10. Änderungs-Log (dieser Plan)

- 2026-06-12 — V0.1: Erstentwurf nach Recherche (Notion-Builder + Who2Be-Seed-
  Architektur). Weichen geklärt: Produkt-Seed + Re-Target. Wartet auf Freigabe.
