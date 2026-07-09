# Builder-Befähigung + Agent-Filter + UI-Polish (Versionen/Playbooks/Persona)

Stand: 2026-07-09 · Branch `claude/builder-agents-ui-improvements-o454yy` · Status: **Aktiv (Plan)**

## Ziel (User-Request)

Zehn Owner-Ideen, gruppiert in sechs unabhängig shippbare Arbeitspakete:
Der Builder soll Placeholder, Persona-Modi und Sub-Playbooks aktiv nutzen
können (statt nur theoretisch); Listen sollen nach Agent filterbar sein;
Versions-Diffs git-artig lesbar werden; die Playbooks-Übersicht
(Trigger-Pills, Composite-Sichtbarkeit, Gruppierung) und die
Persona→Playbook-Sektion werden interaktiv/übersichtlich.

## Ausgangsbefund (verifiziert, 3 Recherche-Agenten 2026-07-09)

- **Placeholder (ADR-0025/0040):** BlockNote-Inline-Blocks `type='placeholder'`
  mit `props {kind, target_id, label}`; 8 Kinds in
  `apps/api/src/who2be_api/services/placeholders/registry.py:63-72`. Render
  über `renderer.py` (Single-Source, nie werfend, Miss → Fallback-String +
  `unresolved_placeholders`). Das Format ist **nur** im Frontend
  (`PlaceholderBlock.tsx`) + Backend-Registry definiert — nicht in
  `packages/models`, nicht serverseitig validiert.
- **Builder kann Templates technisch verfassen** (ADR-0040,
  `create/update_system_prompt`, Capability `system_prompt_write` im
  Builder-Seed), aber: das Seed-Playbook `builder_playbook_agent_body.json:29-30`
  weist ihn an, Templates NICHT via MCP zu bauen (Divergenz zu ADR-0040);
  keine Placeholder-Authoring-Anleitung in irgendeinem Seed; der
  `create_system_prompt`-Docstring (`apps/mcp/.../server.py:986-987`)
  dokumentiert eine veraltete Liquid-`{{…}}`-Syntax, die der Renderer nicht
  kennt.
- **Persona-Modi:** `PersonaVersionContent.modes: list[PersonaMode]`
  (`packages/models/.../persona.py:63-95,140`), via `get/update_persona`
  les-/schreibbar. Keine serverseitige Modus-Auswahl (kein
  `get_persona(mode=…)`, kein REST-Param) — Modus-Wahl ist
  Laufzeit-Anweisung an den Agenten (`resolvers/persona.py:305-313`).
  Builder-Persona selbst ist single-mode; Seeds instruieren Modi nur knapp.
- **Composite-Playbooks (ADR-0024):** vollständig (Link-Tabelle
  `playbook_composition` + position, Zyklen-Guard, `set_playbook_composes`,
  `fetch_playbook` löst genau eine Ebene auf). Builder-Playbook instruiert
  Composites bereits (ab ≥2 Subs, Replace-Semantik) — Token-Spar-Strategie
  (Wiederverwendung vor Neuanlage, Pointer-Embedding) fehlt als explizite
  Anweisung.
- **Agent-Scoping existiert serverseitig komplett:**
  `apps/api/src/who2be_api/core/agent_scope.py` löst
  Agent → persona_playbook → Composite-Closure → resource_links →
  Sub-Resource-Closure per WITH RECURSIVE auf
  (`assigned_playbook_ids`/`assigned_resource_ids`) — heute nur für
  Tool-Policy-Read-Restrict genutzt, kein `?agent=`-Listen-Filter.
- **Versionsanzeige:** `components/version/VersionHistory.tsx` bietet
  Diff/Provenance/Restore. Der Diff (`VersionDiffView.tsx:26-35`) ist ein
  strukturierter Feld-Diff, der geänderte BlockNote-Bodies als
  `JSON.stringify` (200-Zeichen-Cap) zeigt — das ist die vom Owner
  bemängelte „JSON-Anzeige". Einen Voll-Inhalts-Viewer gibt es nicht.
- **Trigger:** `triggers` ist ein kommagetrennter String
  (`packages/models/.../playbook.py:69,147`). Detailseite splittet **nur an
  Kommas** (`features/playbooks/lib/triggers.ts:9-21`) → mit `;` erfasste
  Trigger rendern als eine Riesen-Pill (Owner-Befund bestätigt). Das
  Aggregat `GET /playbooks/triggers` splittet in SQL ebenfalls nur an `,`
  (`playbook_repository.py:675-692`). Die Playbooks-**Liste** zeigt Trigger
  und Composite-Status gar nicht; `composes` fehlt im List-DTO.
- **Persona→Playbook-Sektion** (`PersonaDetailPage.tsx:231-266` +
  `PlaybookLinkItem.tsx`): reines Checkbox-Widget, keine Links/Status/
  Composite-Hinweise.
- **Verteilweg für Builder-Updates existiert:** Seed-JSONs ändern +
  `BUILDER_CONTENT_VERSION`++ → `sync_managed_builder_content` verteilt
  workspace-übergreifend beim API-Start (keine Migration).

## Owner-Entscheidungen (Rückfragen 2026-07-09)

1. **Versionen:** git-orientierte Diff-Darstellung (kein separater
   Vorschau-Viewer beauftragt).
2. **Trigger-Pill:** Ursache sind `;`-getrennte Trigger → Normalisierung
   (Eingabe + Anzeige + Bestand).
3. **Agent-Bezug:** Filter zuerst (Dropdown, `?agent=`); Gruppierung ggf.
   später.
4. **Modi:** „Instruktion + Abruf" — Builder-Seeds forcieren Modi UND
   `get_persona` bekommt einen `mode`-Parameter (serverseitig angewendeter
   Modus); Verwaltung läuft weiter über `update_persona`.

---

## WP-A — Builder-Befähigung (Seeds + MCP-Doku; Backend-only)

Hebt die Divergenz Seed ↔ ADR-0040 auf und macht Placeholder/Modi/
Composites für den Builder **operativ nutzbar**. Kein Web.

1. **Docstring-Fix:** `create_system_prompt`/`update_system_prompt` in
   `apps/mcp/src/who2be_mcp/server.py` — Liquid-Syntax raus, korrektes
   BlockNote-Format rein (Beispiel-JSON eines `placeholder`-Inlines mit
   gültigem `kind`/`target_id`).
2. **Placeholder-Katalog als Tool:** neuer REST-Endpunkt
   `GET /v1/workspaces/{ws_id}/placeholders` (statisch aus `REGISTRY`:
   kind, erlaubte `target_id`-Werte/Semantik, Beschreibung, Beispiel-Inline)
   + dünnes MCP-Read-Tool `list_placeholders`. Damit ist das Format zur
   Laufzeit entdeckbar statt nur im Frontend-Code. (Optionale Folge, nicht
   Teil dieses WP: Write-Zeit-Validierung unbekannter Kinds.)
3. **Seed-Updates (4 Playbooks + Persona, Verteilung via Content-Sync):**
   - `builder_playbook_agent_body.json`: Widerspruch auflösen — Templates
     dürfen via MCP verfasst/angepasst werden (draft→review; Aktivierung
     bleibt Mensch/UI), inkl. Placeholder-Authoring-Abschnitt
     (wann welcher kind, `list_placeholders` zuerst aufrufen).
   - `builder_playbook_persona_body.json`: Modi forcieren — konkrete
     Kriterien (mehrere Einsatz-Stimmen/Output-Formate → Multi-Mode),
     Pflicht-Default-Modus, Trigger-Keywords, `modes`-Schema-Beispiel,
     Hinweis auf `get_persona(mode=…)` (WP-F) für Konsumenten-Agenten.
   - `builder_playbook_playbook_body.json`: Token-Spar-Strategie —
     **vor jeder Neuanlage** `search` + `find_usages` (Wiederverwendung als
     Sub-Playbook statt Duplikat), Pointer-Embedding als Default (inline nur
     begründet), Composite-Zerlegung ab wiederverwendbaren Teilschritten.
   - `builder_playbook_consistency_body.json`: neue Checks — Placeholder-
     Kinds gültig (gegen `list_placeholders`), Trigger normalisiert
     (kommagetrennt), Composite-Kinder aktiv, Modi vollständig
     (bestehender Check bleibt).
   - `BUILDER_CONTENT_VERSION`++; Sync-Test
     (Restaurierung + Idempotenz) um die neuen Inhalte erweitern.

DoD: ruff/mypy clean, pytest (inkl. Sync-Test + neuer Endpoint-/Tool-Tests,
OpenAPI-Golden regeneriert), `--cov-fail-under=85`. Kein ADR nötig
(präzisiert ADR-0040/0025-Umsetzung); DECISIONS-Eintrag.

## WP-B — Agent-Filter auf den Listen (Backend + Web)

1. **Backend:** Query-Param `agent=<uuid>` auf `GET /personas`,
   `GET /playbooks`, `GET /resources` (`routers/personas.py:69`,
   `playbooks.py:85`, `resources.py:69`). Auflösung über die vorhandenen
   `agent_scope`-Queries: Personas → genau `agent.persona_id`; Playbooks →
   `assigned_playbook_ids` (inkl. Composite-Closure); Resources →
   `assigned_resource_ids` (inkl. Sub-Resource-Closure). Unbekannter/
   workspace-fremder Agent → 404. Kombinierbar mit `tag`/`trigger`.
   Repos nutzen die bestehende `restrict_ids`-Mechanik. OpenAPI-Golden.
2. **Web:** `api/client.ts`-Params + `useListFilters` um Facette `agent`
   (URL-Key `?agent=`) erweitern; `ListFilterBar` bekommt ein
   Agent-Dropdown (Agenten via bestehendem `listAgents`); aktiv auf
   PersonasPage, PlaybooksPage, ResourcesPage. Aktiver Filter als
   entfernbarer Chip („Agent: <Name>“). Da der Filter serverseitig wirkt,
   triggert die Facette einen Refetch (anders als die rein clientseitigen
   Facetten) — im Hook sauber trennen.

DoD: Python-DoD wie oben; Web lint/tsc/`test:coverage`/build grün
(Hook-/Bar-/Page-Tests).

## WP-C — Versions-Diff git-artig (Backend + Web)

1. **Backend:** Diff-Endpunkte (`…/versions/{v}/diff`) liefern additiv
   `before_text`/`after_text` — kanonische Markdown-Serialisierung des
   Versions-Contents (Blocks→Markdown-Logik aus den Placeholder-Resolvern
   extrahieren/wiederverwenden, gleiche Reihenfolge/Struktur wie der
   Compose-Render). Bestehende `changes`-Struktur bleibt unverändert.
2. **Web:** `VersionDiffView` rendert für Content einen **unified
   Zeilen-Diff im Git-Stil** (+/−-Zeilen, Kontextzeilen, Hunk-Trenner,
   Mono-Font, Farbflächen über Design-Tokens, `overflow-x: auto`-Container).
   Zeilen-LCS als kleine eigene Utility in `@/lib` (keine neue Dependency
   nötig; falls doch: `diff` ist die Kandidatin — vorher Bundle-Gate
   prüfen). Nicht-Content-Felder (name, tags, triggers, type, …) weiterhin
   als kompakte Feld-Badges. A11y: Diff als `role="table"`/semantische
   Liste mit `aria-label` je Zeilenart.

DoD: beide Stacks grün; Web-Tests für LCS-Utility + Rendering
(added/removed/unchanged, lange Zeilen).

## WP-D — Playbooks-Übersicht: Trigger, Composite, Gruppierung

1. **Trigger-Normalisierung (Quick-Fix zuerst, eigener kleiner PR möglich):**
   - Models: Validator auf `PlaybookContent.triggers` — Split an `,` **und**
     `;`, trim, dedupe (case-insensitiv), Join mit `", "` (Write-Pfad
     normalisiert künftig alles).
   - Frontend: `splitTriggers` auf `/[,;]/` erweitern; `TagInput` im
     Editor-Form serialisiert weiter kommagetrennt.
   - Aggregat-SQL (`playbook_repository.py:675-692`):
     `regexp_split_to_array` über `[,;]`.
   - Migration: Bestand normalisieren — denormalisierte `playbook.triggers`-
     Spalte **und** das `triggers`-Feld der aktuellen Versions-Contents
     in-place (rein syntaktisch, keine inhaltliche Änderung → keine neue
     Version; idempotent).
2. **Listen-Anreicherung:** List-DTO `PlaybookRead` (List-Pfad) additiv um
   `compose_children: list[PlaybookRef]` (Batch-Select über
   `playbook_composition` für die Seite; nur id+name). Web-Liste
   (`PlaybooksPage.tsx:104-131`): Trigger als Einzel-Pills (max. 3 sichtbar
   + „+N“), Composite-Badge, darunter/Popover „komponiert: A · B · C“ mit
   Links zu den Sub-Playbooks.
3. **Übersichtlichkeit/Gruppierung:** Group-by-Selector in der
   `ListFilterBar` (URL `?group=`, Werte `none|type|composite`),
   clientseitig gruppierte `DataList` mit Sektions-Headern + Zählern;
   Zeilen kompakter (eine Zeile Meta). Agent-Filter aus WP-B wirkt
   zusätzlich.

DoD: beide Stacks grün; Migrations-Test (Normalisierung idempotent),
List-DTO-Test, Web-Tests (Pills, Badge, Gruppierung, URL-Sync).

## WP-E — Persona→Playbook-Sektion interaktiv (Web-only)

`PersonaDetailPage`-Sektion umbauen: **Anzeige-Modus** = navigierbare Liste
der verknüpften Playbooks (Link zur Detailseite, `StatusBadge`,
Composite-Badge, Trigger-Anzahl, Typ); **Bearbeiten-Modus** hinter
„Verknüpfungen bearbeiten“-Button (heutiger Checkbox-Picker, ergänzt um
Suchfeld, Speichern/Abbrechen). Bei `is_managed`/Viewer nur Anzeige-Modus.
`usePersonaPlaybooks` liefert dafür die verknüpften Playbooks vollständig
(tut es bereits — `linked` enthält `Playbook[]`).

DoD: Web lint/tsc/`test:coverage`/build grün (beide Modi + locked-Fall
getestet). Kein Python.

## WP-F — Modi serverseitig abrufbar (Backend + MCP)

1. **Render mit Modus:** `persona_service.render` bekommt `mode: str | None`
   — wendet den benannten Modus an (`identity_add` an Profil angehängt,
   `output_style_override` ersetzt Output-Stil, `anti_patterns` ergänzt,
   aktiver Modus markiert); unbekannter Modus → 422 mit Liste verfügbarer
   Modi; ohne Param unverändert (alle Modi als Sektion).
2. **REST:** `?mode=` auf dem Persona-GET/Render-Pfad (additiv).
3. **MCP:** `get_persona(identifier, locale='de', mode=None)`; Docstring
   erklärt den Wechsel-Workflow (Modi aus `content.modes` lesen →
   `get_persona(mode=…)` für den gerenderten Modus). Anweisungstext des
   `persona-ref`-Resolvers (`resolvers/persona.py:306-313`) um den
   `mode`-Param ergänzen.

DoD: Python-DoD grün (Render-Tests je Modus-Feld, 422-Fall,
MCP-Adapter-Test, OpenAPI-Golden). Seeds-Verweis kommt aus WP-A.

---

## Reihenfolge + PR-Schnitt (jedes WP eigener PR, unabhängig shippbar)

| # | WP | Begründung |
|---|----|-----------|
| 1 | D1 (Trigger-Normalisierung) | Kleinster Fix, behebt den sichtbaren UI-Bug sofort |
| 2 | B (Agent-Filter) | Hoher Hebel, Backend-Kette existiert schon |
| 3 | D2+D3 (Playbooks-Liste) | Baut auf D1 auf; größter Übersichts-Gewinn |
| 4 | E (Persona-Sektion) | Klein, Web-only |
| 5 | C (Git-Diff) | Mittel; Backend-Serialisierung + neue Diff-UI |
| 6 | F (Modi-Abruf) | Backend/MCP; Voraussetzung für Seeds-Verweis |
| 7 | A (Builder-Seeds + list_placeholders) | Zuletzt, damit Seeds auf `mode`-Param (F) und normalisierte Trigger (D1) verweisen können |

Abhängigkeiten: B2 braucht B1 (gleicher PR); A verweist auf F + D1 (nur
textuell — A kann notfalls vorgezogen werden, dann Seeds ohne
`mode`-Verweis). Alles andere ist unabhängig.

**Globales DoD je PR** (CLAUDE.md): Python `ruff`/`mypy`/`pytest --cov
--cov-fail-under=85`; Web `npm run lint`/`npx tsc --noEmit`/`npm run
test:coverage`/`npm run build`. Achtung Coverage-Ratchet: der `main`-web-Job
ist aktuell rot (Branch-Coverage-Altschuld, siehe STATE.md) — neue Web-PRs
müssen ihre eigenen Branches voll testen und dürfen den Floor nicht weiter
belasten.

## Bewusst NICHT in diesem Plan (Backlog-Kandidaten)

- Gruppierung der Listen **nach Agent** (Owner: „Filter zuerst“).
- Gerenderte Read-only-Versions-Vorschau (Owner wollte git-Diff).
- Persistenter „aktiver Modus“ pro Agent (state-behaftet; erst wenn
  `get_persona(mode=…)` in der Praxis nicht reicht).
- Write-Zeit-Validierung von Placeholder-Kinds (Soft-Warning) — Folge von
  WP-A, sobald `list_placeholders` da ist.
- Persona-Reverse-Lookup öffentlich (`find_usages` für Personas) — bei
  Bedarf mit WP-B2-Folgearbeiten.
