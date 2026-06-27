# Plan — UX-/Achsen-Verbesserungen: Gruppierung & Arbeitspakete

_Erstellt: 2026-06-27 12:00 · Branch: `claude/gracious-cerf-5ujlj3`_

## Zweck dieses Dokuments

Sammlung von 10 Verbesserungswünschen, gruppiert zu **5 delegierbaren
Arbeitspaketen (WP-A…WP-E)**. Jedes Paket ist eigenständig an einen Agenten
übergebbar und enthält: verifizierter Repo-Befund, Scope, betroffene Dateien,
Akzeptanzkriterien, offene Entscheidungen, Abhängigkeiten. Befunde stammen aus
fünf parallelen Code-Recherchen (2026-06-27) und sind mit Pfaden belegt.

**Zwei Wünsche sind bereits weitgehend implementiert** und brauchen eher
Klärung/Verifikation als Neubau — siehe WP-A §„Bereits gelöst".

### Verriegelte Entscheidungen (User, 2026-06-27)

- **WP-E Konfig-Ebene:** Anker an **allen drei** Ebenen (Persona + Playbook +
  Resource) in einem Zug.
- **WP-B Template-Aktivieren:** Builder erstellt/ändert nur **Draft**; Aktivieren
  bleibt Admin/Mensch (konsistent mit Persona/Playbook-Flow).
- **WP-A Reviewer:** **kein** neues Rollenkonzept — bestehendes Zwei-Gate-Modell
  + dokumentiertes Tool-Policy-Preset „Reviewer" für Agenten.

### Mapping Wunsch → Arbeitspaket

| # | Wunsch | WP |
|---|--------|----|
| 1 | Block-Refs/Placeholder aus Agenten-BlockNotes werden nicht gerendert | **WP-C** |
| 2 | Playbooks gruppierbar nach Agent/Persona + Tags (Filtermenü, keine Suche) | **WP-D** |
| 3 | Agenten sollen reviewen können, nur nicht aktivieren | **WP-A** (+ WP-B) |
| 4 | Builder nutzt Modi nicht — geht das sauber über MCP? | **WP-B** |
| 5 | MCP: Builder soll Systemprompt verwalten können | **WP-B** |
| 6 | Placeholder für Tool-/MCP-Server-Konfig, verankert an Element | **WP-E** |
| 7 | Drafts müssen verwerfbar werden | **WP-A** |
| 8 | Was passiert beim Editieren eines aktiven Elements? Neuer Draft? | **WP-A** (bereits gelöst) |
| 9 | Hinweise für Freigaben (Schnellfreigabe, Prozess verbessern) | **WP-A** |
| 10 | Playbooks und Resources gruppieren & filtern | **WP-D** |

### Empfohlene Reihenfolge / Abhängigkeiten

1. **WP-C** (Bugfix, hoher Wert, isoliert) — kann sofort starten.
2. **WP-A** (Workflow/Freigabe) — fundiert WP-B (Reviewer-Capability).
3. **WP-B** (MCP-Builder) — nach WP-A-Entscheidung zur Reviewer-Granularität;
   teilt das Placeholder-Body-Format mit WP-C (Koordination!).
4. **WP-D** (Listen-Filter) — isoliert Frontend+Backend.
5. **WP-E** (Tool/MCP-Config-Anker) — isoliert, Modell+Migration; teilt
   Renderer-Pfad konzeptionell mit WP-C/WP-B.

---

## WP-A — Versions-/Freigabe-Workflow: Draft verwerfen, Schnellfreigabe, Reviewer

**Wünsche:** #7 (Draft verwerfen), #8 (Edit-auf-Active), #9 (Freigabe-UX),
#3 (Agent: review ja, activate nein).

### Bereits gelöst (nur verifizieren/dokumentieren)

- **#8 Edit-auf-Active → Draft:** `PUT` auf eine aktive Version erzeugt
  automatisch eine neue Draft-Version; existiert schon ein Draft → **409** mit
  klarer Meldung. Implementiert in
  `apps/api/src/who2be_api/services/persona_service.py:221` (`update`, `_draft_conflict()`
  Z. 93), analog Playbook/Resource. Reset `active→draft` reaktiviert die zuvor
  aktive Version automatisch (`persona_service.py:414`). **→ Aufgabe: nur
  verifizieren + im UI sichtbar machen** (Hinweis „Bearbeiten erzeugt einen
  neuen Draft"), kein Neubau.
- **#3 Agent review-but-not-activate (Capability-Ebene):** Das Zwei-Gate-Modell
  kann das schon. `required_role_for_transition(draft, review)` = `editor`;
  `review→active` braucht `admin` **und** Capability `promote_retire`
  (`apps/api/src/who2be_api/services/version_status.py:105`,
  `_require_transition_capability` Z.125-159). Ein Agent-Token mit
  `persona_write`/`playbook_write` aber `promote_retire=false` kann `draft→review`,
  **nicht** `review→active`. **→ Aufgabe: in der Tool-Policy-UI sauber
  exponieren + Default-Preset „Reviewer" anbieten**, ggf. dedizierte
  `review`-Capability (siehe offene Entscheidung).

### Echte Lücken (Neubau)

1. **Draft verwerfen/discarden (#7).** Heute gibt es **keinen** Endpoint, um
   eine einzelne Draft-Version zu löschen. Workaround heute ist umständlich
   (`draft→review→reject` über zwei Rollen) oder brutal (Hard-Delete des ganzen
   Aggregats, ADR-0032). Neu:
   - `DELETE …/{entity}/{id}/versions/{version}` **oder**
     `POST …/versions/{version}/discard`, nur für `status='draft'` (sonst 409).
   - Rollen-Gate: `editor` (Draft verwerfen ist keine Aktivierung).
   - Invariante wahren: nach Discard darf die zuletzt aktive Version aktiv
     bleiben; partielle Unique-Indizes nicht verletzen.
   - MCP-Pendant erwägen (`discard_*_draft`) — siehe WP-B.

2. **Schnellfreigabe / Freigabe-UX (#9).** Heute rendert die `StatusActionBar`
   nur sequenzielle Einzel-Buttons (`Submit`, `Promote`, `Reject`, `Reactivate`)
   — `draft→review` und `review→active` sind zwei Klicks über zwei Rollen.
   - **Quick-Release** für Admins: ein Button `draft→active` in einem Schritt
     (Backend: Hilfs-Transition oder Sequenz `draft→review→active` serverseitig
     atomar; Rollen-Gate `admin`).
   - Freigabe-**Hinweise**: fehlende Pflichtfelder/Composite-Kind-inaktiv schon
     vor dem Klick anzeigen (heute erst als 409 nach Promote,
     `StatusActionBar.tsx:45`).

### Offene Entscheidungen (User)

- **Reviewer-Rolle: ENTSCHIEDEN — kein neues Rollenkonzept.** Bestehendes
  Zwei-Gate-Modell bleibt (`editor` reviewt, `admin` aktiviert); für Agenten
  ein dokumentiertes Tool-Policy-Preset „Reviewer" (siehe WP-B §3). Keine neue
  `reviewer`-Rolle, keine `review`-Capability.
- **Discard-Verb:** `DELETE …/versions/{v}` vs. `POST …/discard`. Empfehlung:
  `POST …/discard` (klare Semantik, keine Verwechslung mit Aggregat-Delete).

### Betroffene Dateien

- State Machine: `packages/models/src/who2be_models/status.py`
- Service/Transition: `apps/api/src/who2be_api/services/version_status.py`,
  `…/services/persona_service.py` (+ playbook/resource analog)
- Router: `apps/api/src/who2be_api/routers/{personas,playbooks,resources}.py`
- Frontend: `apps/web/src/features/personas/components/StatusActionBar.tsx`
  (+ playbooks/resources), `…/features/personas/lib/status.ts`
- RBAC-Test: `apps/api/tests/test_rbac_matrix.py`

### Akzeptanzkriterien

- Editor kann einen Draft verwerfen; danach ist neuer Draft anlegbar; aktive
  Version unberührt; 409 wenn Ziel kein Draft.
- Admin hat einen Quick-Release-Pfad (`draft→active` in einem Schritt).
- UI zeigt vor Freigabe an, was fehlt (statt erst 409).
- Tests: RBAC-Matrix um Discard + Quick-Release erweitert; pytest/ruff/mypy grün.

---

## WP-B — MCP-Builder: Systemprompt-Templates & Modi verwalten

**Wünsche:** #5 (Systemprompt via MCP), #4 (Modi über MCP/Builder),
#3 (Agent-Reviewer-Preset, koordiniert mit WP-A).

### Befund

- **Agent-Modell** (`packages/models/src/who2be_models/agent.py:91`) ist reine,
  **unversionierte** Konfiguration: `persona_id`, `system_prompt_template_id`,
  `status` (enabled/disabled), `tool_policy`. Aktivierbar nur wenn Persona+Template
  gesetzt und Persona eine aktive Version hat.
- **Modi gehören zur Persona, nicht zum Agent** (`persona.py:63` `PersonaMode`:
  `name`, `trigger`, `is_default`, `identity_add`, `output_style_override`,
  `anti_patterns`, `playbook_id`). UI: `PersonaModesEditor.tsx`.
  → Der Builder **kann** Modi heute schon setzen via
  `update_persona(content.modes=…)` — erzeugt aber einen **Draft** (kein
  Auto-Activate, braucht Admin-Promote). Das ist korrekt, aber **nirgends
  dokumentiert**: die MCP-Docstrings (`apps/mcp/src/who2be_mcp/server.py:576`)
  erwähnen `modes` nicht, daher „nutzt der Builder Modi nicht".
- **Systemprompt-Templates: echte Lücke.** Es gibt **keine** MCP-Tools für
  Template-Management. `_WRITE_CAPABILITY` enthält kein `system_prompt_template`,
  Template-Transitions sind für agent-gebundene Tokens **hart gesperrt**
  (`version_status.py:127-159`, 403). Modell+REST existieren bereits
  (`packages/models/src/who2be_models/system_prompt_template.py`,
  `apps/api/src/who2be_api/routers/system_prompts.py`).

### Scope

1. **MCP-Modi sauber machen (#4, klein):** Docstrings von
   `create_persona`/`update_persona` erweitern (Modi-Schema dokumentieren, Beispiel
   inkl. `is_default`/`trigger`); klarstellen, dass Modi→Draft→Promote-Flow gilt.
   Optional: dedizierte Komfort-Tools `set_persona_modes` für sauberere DX.
   Verifizieren, dass der Builder das Schema in der Praxis erzeugen kann (E2E
   gegen MCP).
2. **MCP-Template-Tools (#5, groß):**
   - `create_system_prompt_template`, `update_system_prompt_template`,
     `transition_system_prompt_template`, `restore_system_prompt_template`
     in `apps/mcp/src/who2be_mcp/server.py` (+ Client-Methoden in `client.py`).
   - Neue Capability `template_write` in
     `packages/models/src/who2be_models/tool_policy.py`.
   - `_WRITE_CAPABILITY["system_prompt_template"]` in `version_status.py`
     ergänzen; Template-Transition-Sperre für Agenten lockern (gated auf neue
     Capability + Promote weiterhin admin).
3. **Reviewer-Preset (#3):** In der Agent-Tool-Policy ein dokumentiertes Preset
   „kann reviewen, nicht aktivieren" = `*_write=true`, `promote_retire=false`.
   Koordiniert mit WP-A-Entscheidung.

### Offene Entscheidungen (User)

- **Template-Aktivieren: ENTSCHIEDEN — nur Draft.** Builder darf via MCP
  Templates nur create/update (Draft); Aktivieren (`promote`) bleibt
  Admin/Mensch. Template-Transition-Sperre für Agenten bleibt für `→active`
  bestehen; neue `template_write`-Capability gilt nur für Draft-Schreiben.
- **Komfort-Tool `set_persona_modes`** ja/nein, oder reicht `update_persona`?
  (noch offen, nicht blockierend)

### Betroffene Dateien

- `apps/mcp/src/who2be_mcp/server.py`, `…/client.py`
- `packages/models/src/who2be_models/tool_policy.py`
- `apps/api/src/who2be_api/services/version_status.py`
- (vorhanden, nur nutzen) `…/routers/system_prompts.py`,
  `packages/models/src/who2be_models/system_prompt_template.py`

### Akzeptanzkriterien

- Builder kann via MCP ein Template anlegen/ändern (Draft), scope-korrekt,
  Capability-gegated; Aktivieren bleibt gesperrt/admin.
- `update_persona` mit `modes` ist dokumentiert + per E2E nachgewiesen.
- Agent-Reviewer-Preset existiert und ist in der UI wählbar/dokumentiert.
- pytest/ruff/mypy grün; MCP-Smoke-Test.

---

## WP-C — Bugfix: Placeholder/Block-Refs aus Agenten-erstellten BlockNotes

**Wunsch:** #1. **Höchste Priorität, isoliert lieferbar.**

### Ursachenhypothese (verifiziert)

Der Backend-Extractor erwartet Placeholder-Pills als **Inline-Content innerhalb
eines Blocks**:
```json
[{ "id": "block-id", "type": "paragraph",
   "content": [ {"type":"text","text":"…"},
                {"type":"placeholder","props":{"kind":"resource","target_id":"uuid#block_id",…}} ] }]
```
`extract_pills`/`_walk_block`
(`apps/api/src/who2be_api/services/playbook_body_pills.py`) läuft die `content`-
Arrays der Blöcke ab. Erzeugt ein Agent (über MCP) den Body **ohne** diese
Hüll-Struktur (z. B. Placeholder als Top-Level-Element oder ohne Block-`id`/
`props`), dann:
- Backend extrahiert **keine** Pills (Relations werden nicht synchronisiert,
  `playbook_service.py:_sync_body_pills`), und
- Frontend (`PlaceholderInlineSpec` in
  `apps/web/src/components/editor/system-prompt/PlaceholderBlock.tsx`,
  `SystemPromptEditor.tsx`) rendert nichts, weil die erwartete Inline-Spec-Form
  fehlt.

Kernproblem: **Es gibt keinen kanonischen, validierten Weg, wie ein Agent einen
Body mit Placeholdern erzeugt.** Heute schreibt der Agent rohes BlockNote-JSON
und rät die Struktur. `set_playbook_resource_links`/`set_playbook_composes`
setzen nur Relations, fügen aber **keine** Pills in den Body ein.

### Scope

1. **Kanonisches Body-Format dokumentieren** (Single Source): exakte
   Placeholder-Inline-Struktur (`type`, `props.kind`, `props.target_id`-Format
   `uuid#block_id`, `label`, umschließender Block mit `id`).
2. **Serverseitige Validierung/Normalisierung:** beim Speichern Bodies prüfen;
   fehlerhafte Placeholder-Strukturen entweder reparieren (in Block einwickeln,
   `id` ergänzen) oder mit klarer Fehlermeldung ablehnen. Referenz:
   `agent_builder_body.json` / `builder_playbook_agent_body.json` (korrekte
   Seed-Beispiele).
3. **MCP-DX:** Docstrings von `create_playbook`/`update_playbook`/`create_resource`
   mit Placeholder-Schema + Beispiel; **optional** ein Helfer
   (`insert_resource_pill`) oder ein Schema-Hinweis, damit der Agent Pills
   nicht raten muss.
4. **Frontend robust machen:** `PlaceholderInlineSpec.render` gegen fehlende
   `label`/`target_id` absichern (Fallback-Darstellung statt Leerrendering).

### Betroffene Dateien

- Backend: `apps/api/src/who2be_api/services/playbook_body_pills.py`,
  `…/services/playbook_service.py`,
  `…/services/placeholders/renderer.py`
- Modelle: `packages/models/src/who2be_models/{playbook,resource}.py`
- Frontend: `apps/web/src/components/editor/system-prompt/PlaceholderBlock.tsx`,
  `…/SystemPromptEditor.tsx`,
  `apps/web/src/features/playbooks/lib/bodyMigration.ts`,
  `…/features/playbooks/components/PlaybookBodyEditor.tsx`
- MCP: `apps/mcp/src/who2be_mcp/server.py`, `…/client.py`
- Referenz-Seeds: `apps/api/src/who2be_api/repositories/*body*.json`

### Akzeptanzkriterien

- Ein über MCP erzeugtes Playbook/Resource mit Placeholdern rendert die Pills
  im Web korrekt **und** synchronisiert die Relations (usages stimmen).
- Fehlerhafte Agenten-Bodies werden normalisiert oder mit klarer Meldung
  abgelehnt (kein stilles Leerrendering).
- Reproduzierender Test (Backend: extract_pills auf Agenten-Body; ggf. Web-Test
  auf Render). pytest/vitest/lint/tsc/build grün.

---

## WP-D — Listen: Filtermenü + Gruppierung nach Agent/Persona & Tags

**Wünsche:** #2, #10. Playbooks **und** Resources.

### Befund

- **Heute nur Freitext/Substring-Filter, clientseitig.** Playbooks:
  `PlaybooksPage.tsx` (Tag-/Trigger-Textfeld, `useMemo`). Resources:
  `ResourcesPage.tsx` (klickbare Tag-Badges, Single-Tag).
- **Backend-Bausteine vorhanden:** `GET /playbooks?tag=&trigger=`,
  `GET /resources?tag=`, `GET /playbooks/tags` + `GET /resources/tags`
  (DISTINCT, read-scope-aware). Reverse-Lookups vorhanden:
  `GET /playbooks/{id}/usages` (→ Personas), `GET /resources/{id}/usages`
  (→ Playbooks), `GET /personas/{id}/playbooks`.
- **Es fehlt:** Multi-Tag-Filter, ein Aggregations-/Gruppierungs-Endpoint
  (sonst N+1 über usages), Filter nach Persona/Agent-Zugehörigkeit,
  strukturiertes Filtermenü-UI.

### Scope

1. **Backend:**
   - Multi-Tag-Filter (`?tag=a&tag=b`, AND/OR — Entscheidung unten) für Playbooks
     **und** Resources.
   - Optional `?persona_id=`-Filter für Playbooks (über Persona↔Playbook-Link).
   - Gruppierungsdaten ohne N+1: entweder `?group_by=persona` oder ein
     schlankes Aggregat (Playbook→Personas) in einem Call.
   - Trigger-Filter auch für Resources erwägen (heute nur Playbooks).
2. **Frontend:**
   - Strukturiertes **Filtermenü** (Dropdown/Facetten) statt Freitext:
     Tag-Mehrfachauswahl (aus `/tags`), Typ-Filter (Playbook-Type-Enum),
     Persona/Agent-Auswahl.
   - **Gruppierungs-Selector**: „nach Persona/Agent", „nach Tag", „flach".
   - Resources-Badge-Filter zum gleichen Menü-Muster vereinheitlichen.
   - Hooks erweitern (`usePlaybooks`, `useResources`) für Filter/Group-Params.

### Offene Entscheidungen (User)

- **Multi-Tag-Semantik:** UND (alle Tags) oder ODER (mind. einer)?
  Empfehlung: ODER als Default, UND optional.
- **Gruppieren „nach Agent" vs. „nach Persona":** Playbooks hängen an Personas;
  Agenten referenzieren Personas. „Nach Agent" = transitiv über Persona.
  Reicht „nach Persona", oder beides?

### Betroffene Dateien

- Frontend: `apps/web/src/features/playbooks/pages/PlaybooksPage.tsx`,
  `…/features/resources/pages/ResourcesPage.tsx`,
  `apps/web/src/hooks/{usePlaybooks,useResources,usePlaybookUsages,useResourceUsages}.ts`,
  `apps/web/src/api/{client,types}.ts`
- Backend: `apps/api/src/who2be_api/routers/{playbooks,resources,usages,persona_playbooks}.py`,
  `…/services/{playbook_service,resource_service}.py`,
  `…/repositories/{playbook_repository,resource_repository}.py`

### Akzeptanzkriterien

- Strukturiertes Filtermenü (keine Freitextsuche) für beide Listen.
- Gruppierung nach Persona/Agent **und** nach Tag wählbar, ohne N+1.
- Multi-Tag-Filter funktioniert; read-scope-aware bleibt erhalten.
- lint/tsc/vitest/build + pytest/ruff/mypy grün.

---

## WP-E — Anker für Tool-/MCP-Server-Konfiguration an Element

**Wunsch:** #6. „Placeholder für Tool-/MCP-Server-Konfiguration, fest verankert
in Playbook/Resource/Persona."

### Befund

- **Es gibt heute keinen solchen Anker.** `AgentToolPolicy`
  (`packages/models/src/who2be_models/tool_policy.py:63`) regelt nur
  **Permissions** (welche MCP-Tools ein Agent *darf*), nicht „dieses Element
  bringt diese Tools/MCP-Server mit".
- **Flexibler Einhängepunkt vorhanden:** die `*_version.content` JSONB-Spalten.
  `PersonaVersionContent` (`persona.py:113`), `PlaybookContent` (`playbook.py:44`),
  `ResourceContent` (`resource.py:84`) — aber `extra="forbid"`, daher braucht es
  ein **explizites neues Feld** (kein stilles Wildcard).
- Migrations: nummerierte SQL unter
  `apps/api/src/who2be_api/migrations/` (zuletzt `0051_*`), additive JSONB-
  Evolution (ADR-0009).

### Scope (als ADR + Spike, dann Bau)

1. **Datenmodell:** neues optionales Feld, z. B. `mcp_config` /
   `tool_bindings` in den `*Content`-Klassen (Pydantic). Form klären: Liste von
   `{server_name, url?, tools?: list[str], notes?}` — als „Placeholder/
   Konfigurationsvorlage", nicht als Live-Credential.
2. **Migration:** neue `00NN_*_mcp_config.sql` (additiv, `jsonb`).
3. **Service/Validierung:** Create/Update/Fetch der jeweiligen Services.
4. **Web-Forms:** Feld in `PersonaEditorForm`/`PlaybookEditorForm`/
   `ResourceEditorForm` (+ zugehörige `use*Form`-Hooks).
5. **Optional Renderer:** wenn die Konfig im gerenderten Prompt sichtbar sein
   soll → `services/placeholders/resolvers/` erweitern.

### Offene Entscheidungen (User) — wichtig vor Bau

- **Ebene: ENTSCHIEDEN — alle drei** (Persona + Playbook + Resource) in einem
  Zug. Feld in allen drei `*Content`-Klassen, eine additive Migration deckt alle
  drei Tabellen ab.
- **Was genau speichert das Feld?** Reine Referenz/„Placeholder" (Servername +
  benötigte Tools, ohne Secrets) vs. ausführbare Konfig. Sicherheits-Review
  nötig — **keine** Credentials im versionierten Content (security-reviewer).
- **Verhältnis zu `AgentToolPolicy`:** Element sagt „braucht Tool X", Agent-Policy
  sagt „darf Tool X" — beide getrennt halten, ggf. im UI verknüpfen.

### Betroffene Dateien

- Modelle: `packages/models/src/who2be_models/{persona,playbook,resource}.py`
- Migration: `apps/api/src/who2be_api/migrations/00NN_*_mcp_config.sql`
- Services: `apps/api/src/who2be_api/services/{persona,playbook,resource}_service.py`
- Web: `apps/web/src/features/{personas,playbooks,resources}/components/*EditorForm.tsx`
  + `…/hooks/use*Form.ts`
- Optional MCP: `apps/mcp/src/who2be_mcp/server.py` (Feld in create/update durchreichen)

### Akzeptanzkriterien

- Neues additives Feld speicher- und ladbar; bestehende Inhalte unberührt
  (Migration rückwärtskompatibel).
- UI-Feld vorhanden; keine Secrets im versionierten Content (security-reviewer
  abgezeichnet).
- pytest/ruff/mypy + Web-Gates grün.

---

## Querschnitt / Koordinationshinweise

- **WP-C ⇄ WP-B** teilen das **Placeholder-Body-Format**. Das kanonische Format
  (WP-C §1) muss vor den MCP-DX-Erweiterungen (WP-B/WP-C §3) festgezurrt sein —
  am besten als kurzes ADR.
- **WP-A ⇄ WP-B** teilen die **Reviewer-Granularität** (Capability vs. Rolle).
  WP-A entscheidet, WP-B exponiert das Preset.
- **WP-E** braucht **vor** dem Bau eine User-/Security-Entscheidung (Ebene +
  Inhalt). Bis dahin nur als Spike/ADR delegieren.
- Jedes WP gegen die DoD aus `CLAUDE.md` fahren (Python- bzw. Frontend-Gates).
