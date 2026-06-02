# ADR-0025 — Briefing-Placeholder-Pills (Persona-Referenz, Persona-Modi, Playbook-Katalog)

- Status: Akzeptiert
- Datum: 2026-06-02
- Kontext: Who2Be — System-Prompt-Briefing, BlockNote-Pill-Pfad

## Kontext

Der System-Prompt-Editor (BlockNote-Insel) kennt fuenf Placeholder-Pills:
`playbook`, `resource`, `persona-field` (`name`/`description`/`profile`), `date`,
`tools-overview`. Sie expandieren beim Render serverseitig ueber die
Resolver-`REGISTRY` (`services/placeholders/registry.py`).

Beobachtete Luecke aus der Operator-Sicht „**weiss der Agent nach dem Lesen des
Prompts, was er zu tun hat?**":

1. Persona kann bisher nur **eingebettet** werden (`persona-field:profile`
   tackert einen Snapshot in den Prompt). Es fehlt der Weg, dem Agenten zu
   sagen, dass er seine Persona **selbst zur Laufzeit via MCP** holen soll —
   kleinerer Prompt, frischere Daten.
2. Persona-Modi sind nur als Teil des vollen Profils einbettbar, nicht
   eigenstaendig.
3. Es gibt keine kompakte, handlungsorientierte **Uebersicht** der dem Agenten
   zur Verfuegung stehenden Playbooks (welche, wann, wie aufrufen). Der Agent
   muss alles ueber `list_triggers()` selbst entdecken.

## Optionen

### A — Nur Doku/Default-Templates anpassen

Briefing-Hinweise im Default-Template-Seed verbessern. Verworfen: loest die
fehlende **dynamische** Persona-Referenz und die **datengetriebene**
Playbook-Tabelle nicht; reiner Freitext veraltet.

### B — Plain-`{{ }}`-Engine erweitern

Neue Liquid-Tokens in `agent_render_service.py`. Verworfen (User-Entscheidung):
der Plain-Pfad ist Legacy; der Pill-Editor ist die aktuelle UX. Doppelpflege
vermeiden.

### C — Neue Pill-Kinds im BlockNote-Pfad (gewaehlt)

Drei Erweiterungen, jeweils 1 Resolver + Registry-Eintrag + Frontend-Spiegelung:

- **`persona-ref`** (neu, parameterlos): rendert eine **Anweisung** statt
  Inhalt — Name + ID der Persona plus die Aufforderung, sie via
  `get_persona("<id>")` zu laden und die Modi anzuwenden.
- **`persona-field:modes`** (Erweiterung): rendert nur die `## Modi`-Sektion;
  ohne Modi ein leerer String (kein Miss — Modi sind optional).
- **`playbooks-catalog`** (neu, mit Pill-Setting): Markdown-Tabelle der
  persona-verknuepften aktiven Playbooks mit Spalten **Playbook | Trigger |
  Aufruf | Beschreibung**. Die `Aufruf`-Spalte enthaelt den konkreten
  `fetch_playbook("<id>")`-Call. Setting `target_id ∈ {all, triggered}` steuert,
  ob nur Playbooks mit Trigger gelistet werden.

## Entscheidung

**Option C.**

### Scope-Entscheidungen (vom User gesperrt)

- **Persona:** beide Wege anbieten — Einbetten (`persona-field`, erweitert um
  `modes`) **und** dynamische Referenz (`persona-ref`).
- **Katalog-Quelle:** persona-verknuepfte Playbooks (`persona_playbook`),
  konsistent mit `{{ playbooks }}` / `list_triggers`-Semantik.
- **Katalog-Spalten:** Name, Trigger, Aufruf, Beschreibung.
- **Render-Pfad:** ausschliesslich BlockNote-Pills; Plain-`{{ }}`-Engine und
  Default-Template-Seed bleiben unveraendert.

### Resolver-Verhalten (Agent- und Editor-Perspektive)

- `persona-ref`: Miss (leerer String + `persona-ref:`-Key), wenn keine Persona
  im Kontext oder nicht gefunden. Sonst Briefing-Zeile mit `id` + `get_persona`.
- `persona-field:modes`: Modi vorhanden → `## Modi`-Sektion; keine Modi →
  leerer String, **kein** Miss.
- `playbooks-catalog`: `persona_id is None` → Miss (im Editor-Preview ohne
  Persona-Kontext zeigt das den Laufzeit-Hinweis, statt einer irrefuehrend
  leeren Tabelle). Persona vorhanden, aber keine (passenden) Playbooks →
  kurzer Hinweistext (kein Miss). Filter `triggered` schliesst trigger-lose
  Playbooks aus. Tabellen-Zellen escapen `|` und kollabieren Newlines.

Alle Pills filtern Playbooks/Resourcen auf `status='active'` — analog den
MCP-Reads und der Applied-Pill (keine Drafts im Agenten-Prompt).

## Konsequenzen

- `REGISTRY` erhaelt `persona-ref` + `playbooks-catalog`; `PersonaFieldResolver`
  akzeptiert zusaetzlich `modes`. Additiv — bestehende Templates brechen nicht.
- Der `placeholder-preview`-Endpoint funktioniert ohne Aenderung (generisch
  ueber `REGISTRY`).
- Frontend: neue Kinds in `PlaceholderBlock` (Schema, Pill-Tinte
  `pill-catalog`), Slash-Items, `CatalogScopePicker`, `PersonaFieldPicker`-Option
  `modes`. `persona-ref` ist parameterlos (Direkt-Insert wie `tools-overview`);
  `playbooks-catalog` nutzt einen Scope-Picker.
- Die Modi-Sektion ist als `_render_modes_section` aus `_render_persona_profile`
  herausgeloest (Single-Source, von `profile` **und** `modes` genutzt).
