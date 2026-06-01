# Plan: Rich-Modi, Modell-Lücken & Inline-Slash-Links (Playbook-Compose)

**Status:** Entwurf — wartet auf Freigabe
**Datum:** 2026-06-01
**Branch:** `claude/relaxed-goldberg-BSyuM`
**Auslöser:** User-Fragen 1–7 zur Agenten-Persönlichkeit/Playbook-Mechanik.
Fragen 1–3 sind Analyse (siehe unten „Kontext"), 4–7 sind die hier geplanten
Änderungen.

## Design-Entscheidungen (vom User bestätigt 2026-06-01)

1. **Inline-Links Source-of-Truth:** *Body treibt, Sync zu Tabellen.* Inline-Pills
   im Playbook-BlockNote-Body sind die Editier-Oberfläche; beim Speichern leitet
   das Backend daraus die Relation-Sets ab und schreibt sie in die bestehenden
   Tabellen (`playbook_composition`, `playbook_resource_link`). Resolver,
   Backlinks und MCP `fetch_playbook` bleiben auf den Tabellen → stabil.
   Einfügen einer Playbook-Pill = Compose.
2. **Modi-Editor:** *BlockNote pro Langfeld.* `identity_add` und
   `output_style_override` werden je eine kleine BlockNote-Insel
   (`ResourceBlock[]`), Record-Felder (`name`/`trigger`/`is_default`) bleiben
   Formular.
3. **Modell-Lücken:** *Alle drei jetzt* — `mode.playbook_id`, per-mode
   `anti_patterns`, `persona.skills`.

## Kontext / warum (Fragen 1–3, nur Doku, kein Code)

- **F1 (woher Persönlichkeit):** zwei Ebenen — Deployment-Bootstrap (ein
  gepinnter Zeiger in CLAUDE.md/Project-Instructions: `fetch_agent(agent_id)`)
  + server-seitige Auflösung (`{{ persona profile }}` expandiert beim Boot).
- **F2 (welche Playbooks wann):** Applied (Pill, immer) vs. Triggered
  (`list_triggers` → Keyword-Match → `fetch_playbook`). Siehe `docs/agent-axes.md`.
- **F3 (Brainstormer abbildbar):** Kern ja; Lücken = Mode→Playbook-Bindung,
  per-mode Anti-Patterns, Skills, Rich-Text-Modi. Genau diese werden hier
  geschlossen.

## ⚠️ Kritische Revision (2026-06-01, nach Code-Verifikation)

Eine tragende Annahme der Erstfassung war falsch. Korrekturen:

1. **Playbook-Body ist heute Plain-`str`** (`playbook.py:49`); der Editor
   serialisiert via `blocksToPlainText` (`usePlaybookForm.ts:38-46,73`).
   Inline-Pills überleben einen Save **nicht**. → **Body-Format-Migration
   (`blocknote`-JSON + `body_format`-Spalte, Muster wie `system_prompt_template`
   / Migration 0026) ist Pflicht-Fundament**, nicht Fußnote.
2. **Block-Anker ist Requirement** (Frage 6 = „Resourcen *Blöcke* verlinken").
   `ResourceResolver` kann heute nur ganze Resourcen (kein `#block_id`,
   `registry.py:179-233`). → Resolver + Pill-Props + Picker müssen Block-Level
   können, sonst Regression ggü. `ResourceBlockLinkPicker`.
3. **„Body treibt" + Set-Replace = Datenverlust** für Bestands-Playbooks
   (Plain-Body, aber Relationen in Tabellen). → Backfill: Relationen beim
   Konvertieren als Pills in den Body injizieren, oder Sync additiv/gegated.
4. **`_render_persona_profile` ist pure/sync, kein DB** (`registry.py:348`).
   `mode.playbook_id`→Name: **denormalisierter `playbook_name`-Snapshot** im
   Modus (statt DB-Plumbing).
5. **`fetch_playbook` rendert den Body heute NICHT** (`server.py:179-214`, roh).
   Für Pill-Expansion muss der Playbook-Body durch `render_template_body`.
6. **Zwei Composite-Mechaniken**: `playbook_composition` + `## Ablauf`-Render vs.
   neue Body-Pill. Rendering-Vertrag nötig (Pill = inline Erwähnung, `## Ablauf`
   = maßgebliche Sequenz).

**Scope-Schnitt:** Persona-Seite und Playbook-Seite sind unabhängig; die
Playbook-Seite ist deutlich schwerer. → **Zwei getrennte PRs/Inkremente**
(siehe revidierte Wellen unten).

## Architektur-Notizen

### Persona-Modi (Backend-Vertrag)
`PersonaMode` heute (`packages/models/.../persona.py:19-36`):
`name, trigger, is_default, identity_add: str, output_style_override: str`.

Neu:
- `identity_add: list[ResourceBlock]` (war `str`)
- `output_style_override: list[ResourceBlock]` (war `str`)
- `anti_patterns: list[ResourceBlock] = []` (neu)
- `playbook_id: UUID | None = None` (neu — Mode→Playbook-Bindung)

`PersonaVersionContent` (`persona.py:54-106`):
- `skills: list[SkillRef] = []` (neu). `SkillRef = {name: str, note: str}`
  (note = Relevanz-Hinweis wie in Brainstormer-Persona).

**Backward-Compat / Migration:** `persona_version.content` ist `jsonb`
(`persona_repository.py:149`). Alte Versionen haben `identity_add` als String.
→ Migration `0029` braucht **kein** Spaltenschema, aber wir brauchen eine
**Lese-Koerzion**: beim Deserialisieren einen `field_validator(mode="before")`
auf `identity_add`/`output_style_override`, der einen vorhandenen `str` in einen
einzelnen Paragraph-`ResourceBlock` wrappt (alt → neu, verlustfrei lesbar).
Damit bleiben gespeicherte Alt-Versionen valide, ohne Daten-Backfill.

### Resolver-Rendering (`services/placeholders/registry.py::_render_persona_profile`, ~348-415)
- `identity_add`/`output_style_override`/`anti_patterns` jetzt über die
  vorhandene `_block_plain_text`-Block-Serialisierung rendern (statt `str`).
- Neue Sektion `### Anti-Patterns` je Modus (falls vorhanden).
- Pro Modus mit `playbook_id`: Zeile „**Zugehöriges Playbook:** <Name>" rendern
  (Name via Lookup; bei inaktiv/gelöscht überspringen, analog Composite-Logik).
- Neue `## Skills`-Sektion im Profil (falls `skills` vorhanden).

### Playbook-Body Inline-Pills (Frage 6+7)
Das Muster existiert vollständig im **SystemPromptEditor** — wird übertragen:
- `PlaceholderInlineSpec` (`components/editor/system-prompt/PlaceholderBlock.tsx:75-135`)
  mit `kind ∈ {playbook, resource, …}`, `target_id`, `label`.
- `buildSlashMenuItems` (`slashMenu.ts:54-109`) — „Playbook" + „Resource"-Items
  mit Picker-Callback.
- `SuggestionMenuController` + Picker-Dialog.

Heute nutzt der Playbook-Editor den **generischen** `BlockNoteEditor`
(`components/editor/BlockNoteEditor.tsx`, kein Schema, kein Slash). Wir geben
ihm ein Custom-Schema (resource + playbook Pills) — entweder durch Parametrisieren
des `BlockNoteEditor` oder einen dedizierten `PlaybookBodyEditor` (Entscheidung
in Schritt 2.2; Default: dediziert, um die generische Insel unangetastet zu lassen).

**Save-Sync (Body treibt):** Beim Speichern des Playbooks
(`playbook_service.update*`):
1. Body-Blocks nach `kind=playbook`-Pills scannen → geordnete `child_ids` →
   `set_composition()` (`playbook_composition_repository`).
2. Body-Blocks nach `kind=resource`-Pills scannen → `ResourceLinkItem`-Set
   (Dokument-Reihenfolge → `position`; `block_id`/`link_scope` aus Pill-Props) →
   `set_links()` (`playbook_resource_link_repository`).
Damit ist der Body der einzige Schreiber für pill-stämmige Links.

**fetch_playbook-Expansion:** `composed_playbooks` und `linked_resources` kommen
weiterhin aus den Tabellen (MCP `server.py:178-214`) — **kein** Body-Parsing im
MCP nötig, weil der Sync die Tabellen aktuell hält. Der gerenderte Body für den
Agenten muss die Pills aber zu lesbarem Text expandieren (Resolver-Pfad wie
beim Template-Body). Verifizieren, ob der Playbook-Body heute durch
`renderer.py` läuft; falls nicht, beim Render-Schritt ergänzen.

### Offener Mikro-Punkt (vor Umsetzung kurz bestätigen)
Die bestehenden Dialoge `PlaybookComposesPicker` / `ResourceBlockLinkPicker`
würden bei „Body treibt" beim nächsten Body-Save **überschrieben**. Vorschlag:
Dialoge auf **read-only Backlink-/Übersicht** zurückstufen (nicht löschen),
Editier-Pfad konvergiert auf den Body. → Bestätigung einholen, bevor ein
user-sichtbarer Dialog entfernt/entwertet wird (kein eigenmächtiges Löschen).

## Wellen — zwei getrennte Inkremente (PR-A Persona, PR-B Playbook)

### PR-A — Persona: Rich-Modi + Mode→Playbook + Anti-Patterns + Skills ✅ ERLEDIGT (2026-06-01)
Self-contained, kleineres Risiko, kein Body-Format-Umbau. Commit `9ccc799`.
Gates: pytest 338 passed / ruff / mypy 150; web tsc / lint(0 err) / 268 tests / build.

- **A0 Fundament** `packages/models/.../persona.py`: `identity_add`/
  `output_style_override` → `list[ResourceBlock]`; neu `anti_patterns:
  list[ResourceBlock]`, `playbook_id: UUID|None`, `playbook_name: str` (Snapshot,
  bei Save gesetzt). `PersonaVersionContent.skills: list[SkillRef]` (+ `SkillRef`).
  **Read-Koerzion** `field_validator(mode="before")`: Alt-`str` → ein
  Paragraph-Block, verlustfrei lesbar; kein DB-Backfill. Migration `0029` nur
  Doku-Kommentar (jsonb additiv).
- **A1 Resolver** `registry.py::_render_persona_profile` (348-415): Modi-Felder
  via `_block_plain_text` (statt `str(...)`, Zeilen 398-411); `### Anti-Patterns`
  je Modus; `**Zugehöriges Playbook:** {playbook_name}` je Modus; `## Skills`.
- **A2 Frontend** `features/personas/`: `PersonaModesEditor` — BlockNote-Insel je
  `identity_add`/`output_style_override`/`anti_patterns`, Per-Mode Playbook-Picker
  (setzt id+name), Skills-Input. `usePersonaForm` + `api/types.ts`.
- **A3 Tests + Doku**: Resolver/Service (Alt-str-Koerzion, Block-Render,
  Mode-Playbook, Skills), Vitest Modi-Editor. `docs/agent-axes.md`.

### PR-B — Playbook: Slash-Links + Body-Format + Block-Anker + Sync
Schwerer; setzt das Body-Format-Fundament voraus.

- **B0 Body-Format-Fundament** (blockierend): `PlaybookContent` +
  `body_format ∈ {plain,blocknote}` (Modell + Migration analog
  `0026_system_prompt_template_body_format.sql`); `usePlaybookForm` speichert
  BlockNote-JSON statt `blocksToPlainText`.
- **B1 Block-Anker im Resolver** `ResourceResolver` (registry.py:179-233):
  optionalen `block_id`/Block-Slice-Support (Pill-Prop trägt block_id).
- **B2 Body-Render-Verdrahtung**: `fetch_playbook` (MCP `server.py:179-214`)
  leitet `body_format='blocknote'`-Bodies durch `render_template_body`;
  Composite-Pill-Rendering-Vertrag (Pill inline, `## Ablauf` maßgeblich).
- **B3 Save-Sync (Body treibt)** `playbook_service` + Repos: aus Body-Pills
  `set_composition` (playbook-Pills, Dok-Reihenfolge) + `set_links`
  (resource-Pills inkl. block_id/scope) ableiten. **Backfill**: bestehende
  Tabellen-Relationen bei Konvertierung als Body-Pills injizieren — sonst
  Datenverlust.
- **B4 Frontend** `features/playbooks/`: `PlaybookBodyEditor` (Custom-Schema
  resource+playbook Pills, Slash-Items + Picker mit Block-Auswahl). Dialoge
  `PlaybookComposesPicker`/`ResourceBlockLinkPicker` → read-only Übersicht
  (nach Bestätigung Mikro-Punkt; nicht löschen).
- **B5 Tests**: `test_placeholder_renderer` (Block-Anker), `test_playbook_*`
  (Body→Tabellen-Sync, Backfill-Roundtrip), `compose-smoke` grün; Vitest Pills.

### Abschluss je PR
Beide Stacks grün (`uv run pytest -q`, `ruff`, `mypy`; `npm run lint`,
`tsc --noEmit`, `npm test`, `npm run build`), `docs/` + Notion-Change-Log +
Pointer, Conventional-Commit + Push + Draft-PR.
- Commit (Conventional Commits) + Push + Draft-PR.

## Completion-Condition (`/goal`-Stil, messbar)
- Brainstormer-Persona (4 Modi mit Rich-Content + Mode-Playbooks + Skills) ist
  über die Web-UI vollständig anlegbar und `fetch_agent`/`get_persona` rendern
  Modi-Blöcke, Anti-Patterns, Mode-Playbook und Skills korrekt (Test-Nachweis).
- Im Playbook-Editor lassen sich per Slash Resource- und Playbook-Pills einfügen;
  Speichern erzeugt/aktualisiert `playbook_composition` + `playbook_resource_link`
  (Test-Nachweis); `fetch_playbook` liefert konsistente `composed_playbooks` /
  `linked_resources`.
- Alle Lint/Type/Test/Build-Gates beider Stacks grün (transkript-nachweisbar).

## Risiken
- jsonb-Alt-Daten (`identity_add` als String) → durch Read-Koerzion abgedeckt;
  Test mit Alt-Snapshot.
- Doppel-Schreiber (Body-Sync vs. Alt-Dialoge) → Dialoge entwerten (Mikro-Punkt).
- Pill-Expansion-Pfad für Playbook-Body evtl. noch nicht vorhanden → in 1.3
  zuerst verifizieren, dann ergänzen.
```
