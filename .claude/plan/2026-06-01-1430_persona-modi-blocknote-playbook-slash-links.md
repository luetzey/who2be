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

## Wellen (datei-disjunkt, nach Plan-Freigabe an Sub-Agents verteilt)

### Welle 0 — Fundament (zuerst, blockierend, sequenziell)
- **0.1 Models** `packages/models/.../persona.py`: `PersonaMode`-Felder
  (Blocks + `anti_patterns` + `playbook_id`), `PersonaVersionContent.skills`,
  `SkillRef`, Read-Koerzion-Validator (str→Block). `playbook.py`: ggf.
  `body_format`-Marker prüfen/ergänzen.
- **0.2 Migration** `migrations/0029_persona_modes_skills.sql`: nur falls
  DB-Constraints/Kommentare nötig (jsonb additiv → vermutlich nur
  Doku-Kommentar + evtl. CHECK). ADR-0009/0024-Notiz ergänzen.
- **0.3 ADR**: kurzer ADR-Eintrag „Rich-Modi + Mode→Playbook + Body-driven
  Links" (Notion + `docs/`).

### Welle 1 — Backend (nach Welle 0; intern paketiert, da Dateien überlappen)
- **1.1** `registry.py::_render_persona_profile` — Block-Render für Modi-Felder,
  Anti-Patterns, Mode-Playbook-Name, Skills-Sektion.
- **1.2** Playbook-Save-Sync — `playbook_service` + beide Repos
  (`set_composition`/`set_links` aus Body-Pills ableiten).
- **1.3** Playbook-Body-Pill-Expansion im Render-/`fetch_playbook`-Pfad
  (`renderer.py` / MCP `server.py`) — nur falls heute nicht abgedeckt.
- **1.4** Backend-Tests: `test_persona_service`, `test_placeholder_renderer`,
  `test_playbook_composition`, `test_playbook_resources` (Alt-String-Koerzion,
  Mode-Playbook-Render, Body→Tabellen-Sync, Pill-Expansion).

### Welle 2 — Frontend (nach Welle 0/1-Contract; 2.1 ∥ 2.2 disjunkt)
- **2.1 Personas** (`features/personas/`): `PersonaModesEditor` — BlockNote-Insel
  je `identity_add`/`output_style_override`, Anti-Patterns-Insel, Per-Mode
  Playbook-Picker, Skills-Input (TagInput-artig + Note). `usePersonaForm`/Types
  (`api/types.ts`) anpassen (Blocks statt str, neue Felder).
- **2.2 Playbooks** (`features/playbooks/`): `PlaybookBodyEditor` mit
  Custom-Schema (resource + playbook Pills), Slash-Items (Resource/Playbook) +
  Picker, Save-Wiring (Body → bestehende Mutations-/Sync-Calls). Dialoge
  `PlaybookComposesPicker`/`ResourceBlockLinkPicker` auf read-only zurückstufen
  (nach Bestätigung Mikro-Punkt).
- **2.3 Frontend-Tests**: Vitest für Modi-Editor + Playbook-Slash/Pill-Insert.

### Welle 3 — Verifikation & Doku
- Beide Stacks grün: `uv run pytest -q`, `uv run ruff check .`, `uv run mypy .`;
  `npm run lint`, `npx tsc --noEmit`, `npm test`, `npm run build`.
- `docs/agent-axes.md` + `docs/CLAUDE-PROFILE.md` updaten.
- Notion-Change-Log in Projekt-`## Notes` + Pointer auf diese Datei.
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
