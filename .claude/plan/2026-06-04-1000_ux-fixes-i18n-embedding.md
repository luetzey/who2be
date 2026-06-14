# Plan — UX-Fixes, i18n & Embed-Modi (5 Themen → 2 Wellen)

**Status:** Aktiv — Agenten werden vom User manuell gestartet (getrennte PRs pro Thema).
**Erstellt:** 2026-06-04. **Branch-Strategie:** ein Branch + Draft-PR pro Stream.

## Kontext

Fünf vom User gewünschte Änderungen, vor der Planung per fünf Explore-Agenten
im Code verifiziert:

1. **Dashboard-API-Fehler** „Who2Be-API nicht erreichbar." — String aus
   `apps/web/src/api/client.ts:89` (fetch schlägt fehl). Verdächtige Ursachen:
   fehlende `.env` (`config.ts:26`), leere Workspace-ID →
   `/v1/workspaces//dashboard` (`useWorkspaceId.ts:9-16` gibt leeren String),
   oder API down.
2. **Agent-Erstellung vereinfachen** — aktuell ZWEI Buttons in
   `features/agents/pages/AgentsPage.tsx:47-64`. Agent-Konzept (= Persona +
   System-Prompt-Template, Status enabled/disabled, `is_shell`-Logik in
   `packages/models/agent.py:94-99`) existiert; DB-Refs sind seit
   `0034_agent_optional_refs.sql` optional. Copy ist bei Shell schon gesperrt
   (`agent_service.py:110-137`).
3. **i18n DE/EN** — keine i18n-Infrastruktur, ~390 hartkodierte DE-Strings.
   `placeholders/registry.py` kennt bereits `locale`.
4. **Embed standardmäßig nur als Link** — MCP sendet aktuell `link_scope=='resource'`
   VOLL inline (`apps/mcp/.../server.py:226-231`). Kein Link-vs.-Fest-Flag.
5. **Resource→Resource-Verkettung** — backendseitig ~95% fertig (Migration
   `0032`, `resource_composition_*`, MCP `fetch_resource:308`); `SubResourcePicker`
   im Frontend gelistet, Verdrahtung prüfen.

## User-Entscheidungen (2026-06-04)

| Frage | Entscheidung |
|---|---|
| i18n-Umfang | **UI + Inhalte (Voll)** — Agents/Personas/Playbooks/Resources als echte DE+EN-Varianten |
| Agent-Aktiv-Regel | **Persona + Template gesetzt UND verknüpfte Persona im Status `active`** |
| Liefer-Strategie | **Getrennte PRs pro Thema**; i18n zeitlich entkoppelt |
| Dashboard-Fix | **Erst Ursache reproduzieren/verifizieren, dann fixen** |

## Repo-Fakten (für Migrationen/Konflikte)

- Migrationen stehen bei **`0039`** (`NNNN_desc.sql`, Runner `uv run who2be-migrate`,
  idempotent via `schema_migrations`). Nächste frei = `0040`.
- Frontend-Feature-Ordner sind disjunkt (`features/{dashboard,agents,resources,
  playbooks,personas}`), Backend-Services getrennt → 3 echt-parallele Streams
  möglich. **i18n überlappt mit allem** (String-Extraktion = alle Frontend-Dateien;
  Content-Modell = `packages/models` + Migrationen + MCP).

## Wellen-Schnitt

| Stream | Backend | Frontend | Migration | Welle |
|---|---|---|---|---|
| **A Dashboard-Fix** | `dashboard_*`, `client.ts`, `config.ts`, `useWorkspaceId` | `features/dashboard` | – | 1 |
| **B Agent-Flow + Aktiv-Regel** | `agent_service.py`, `agents.py`, `models/agent.py` | `features/agents` | – | 1 |
| **C Embed-Modus + Resource-Compose** | `models/{resource,playbook,links}`, link/composition-Repos, `apps/mcp/server.py` | `features/{resources,playbooks}` | **0040, 0041** | 1 |
| **D1 i18n UI** | (User-Pref-Persist) | **alle** `features/**` | – | 2 |
| **D2 i18n Content** | `models/{persona,playbook,resource}`, alle `*_version`-Tabellen, `apps/mcp/server.py`, API-Router | Create-Flows | **0042+** | 2 |

**i18n in Welle 2**, weil D1 dieselben Frontend-Dateien wie B/C editiert und D2
dieselben Models/MCP/Migrationen wie C. Start nach Merge von A/B/C → sauberer
Rebase, null Dauer-Konflikte.

## Koordinationsregeln (alle Agenten)

1. **Migrationsnummern fest:** C = `0040/0041`, D2 = ab `0042`. Sonst niemand.
2. **`packages/models/__init__.py` (Barrel)** ist die einzige potenziell von
   mehreren Streams berührte Datei (je 1 Export-Zeile) → trivialer Merge.
3. **Welle 2 erst nach Merge von Welle 1**; D1/D2 rebasen auf `main`.
4. **Je Stream eigener Branch + Draft-PR.** CLAUDE.md-DoD lokal grün vor Push.
5. Repo-Konventionen + Skills `python-conventions`/`react-conventions` gelten
   (keine direkten `<button>`/`<input>`, Tokens statt hex/px, Conventional Commits).

---

# Agenten-Prompts

## Welle 1 — drei parallele Agenten

### Agent A — Dashboard-Fix (erst verifizieren, dann fixen)

```
Branch: fix/dashboard-api-erreichbar

Kontext: Im Who2Be-Web-UI zeigt das Dashboard den Fehler „Who2Be-API nicht
erreichbar." Der String wird in apps/web/src/api/client.ts:89 geworfen, wenn
fetch() fehlschlägt. Verdächtige Ursachen: (a) fehlende .env → VITE_API_BASE_URL
undefiniert (config.ts:26 fällt auf http://localhost:8000), (b) leere Workspace-ID
→ Request geht an /v1/workspaces//dashboard (useWorkspaceId.ts:9-16 gibt bei
fehlendem Param + fehlender default_workspace_id einen LEEREN String zurück),
(c) API läuft nicht.

AUFGABE — Schritt 1 (Verifikation, PFLICHT zuerst):
Fahre API + Web lokal hoch (uv run uvicorn who2be_api.main:app; in apps/web
npm run dev; docker compose up -d falls DB nötig). Reproduziere den Fehler.
Stelle über DevTools/curl fest, WELCHE URL real gerufen wird und mit welchem
Status sie fehlschlägt. Halte die echte Ursache fest, bevor du fixt.

AUFGABE — Schritt 2 (Fix der echten Ursache + Härtung):
- Behebe die identifizierte Ursache.
- Härte useWorkspaceId / den Dashboard-Hook: Wenn keine Workspace-ID vorliegt,
  KEINEN /v1/workspaces//... Request feuern, sondern einen sinnvollen Zustand
  zeigen (Loading/„Workspace wird vorbereitet"), nicht den generischen
  „nicht erreichbar"-Fehler.
- Falls .env-Handling die Ursache ist: .env.example prüfen, Default robust machen,
  ggf. .env anlegen/dokumentieren — KEINE Secrets committen.
- Optional: Fehlermeldung in client.ts:87-89 so loggen, dass Ursache erkennbar ist.

NUR diese Dateien/Bereiche anfassen: apps/web/src/features/dashboard/**,
apps/web/src/api/client.ts (nur Dashboard/Fehlerpfad), apps/web/src/config.ts,
apps/web/src/auth/useWorkspaceId.ts, apps/api/.../routers/dashboard.py +
services/dashboard_service.py + repositories/dashboard_repository.py NUR falls
der echte Bug dort liegt. NICHT features/agents, resources, playbooks anfassen.

DoD: Dashboard rendert lokal mit KPIs/Activity. npm run lint, npx tsc --noEmit,
npm test, npm run build grün. Backend: uv run pytest -q (zumindest
test_dashboard_*), ruff, mypy grün. Draft-PR mit Reproduktions-Beschreibung +
Root-Cause + Fix.
```

### Agent B — Agent-Erstellung vereinfachen + Aktiv-Regel

```
Branch: feat/agent-create-flow-activation

Kontext: Das „Agent"-Konzept (= Persona + System-Prompt-Template, Status
enabled/disabled, is_shell-Logik in packages/models/agent.py:94-99) existiert.
Aktuell hat apps/web/.../features/agents/pages/AgentsPage.tsx:47-64 ZWEI
Erstell-Buttons: „Neuer leerer Agent" (Shell) und „Neuer Agent" (/agents/new,
erzwingt Persona+Template vorab). DuplicateAgentButton + agent_service.py:110-137
sperren Copy bereits, wenn is_shell.

ZIEL-UX: Genau EIN Button „Neuen Agent erstellen". Er legt immer einen leeren,
sofort speicherbaren Agent an. Der User kann alles frei eingeben und JEDERZEIT
speichern, ohne Pflichtfeld-Zwang (kein „alles ausfüllen müssen" im Flow).
Aber: Aktivieren (enabled) UND Kopieren sind nur möglich, wenn der Agent
VOLLSTÄNDIG ist. Vollständig = Persona verknüpft UND Prompt-Template verknüpft
UND die verknüpfte Persona ist selbst im Status 'active' (nicht nur Draft).
Solange unvollständig: speicherbar, aber disabled + nicht kopierbar, mit klarer
Anzeige, WAS noch fehlt.

AUFGABE:
- Frontend: Zweiten Button + /agents/new-Pfad entfernen (AgentNewPage löschen
  oder auf den Empty-Create-Flow umleiten). „Neuer leerer Agent" → „Neuen Agent
  erstellen". AgentEditorForm: Persona/Template optional, kein Submit-Zwang.
- Backend: agent_service Enable-Transition + Copy gaten auf neue Bedingung
  (Persona+Template gesetzt UND Persona-Status == active). Liefere im AgentRead
  ein „activatable: bool" + „missing: list[str]" (z.B. ["persona","template",
  "persona_active"]), damit das Frontend genau anzeigen kann, was fehlt.
  is_shell entsprechend erweitern/ergänzen.
- Aktivieren-/Kopieren-Buttons im Frontend disabled + Tooltip mit fehlenden
  Punkten, wenn nicht activatable.

NUR anfassen: apps/web/src/features/agents/**, apps/api/.../routers/agents.py,
services/agent_service.py, packages/models/agent.py (+ dessen Barrel-Export in
who2be_models/__init__.py — koordiniere diese eine Zeile vorsichtig).
NICHT version_status.py / promote_validation.py ändern (Persona-Status nur LESEN).
NICHT features/personas, dashboard, resources anfassen.

DoD: Neuer Agent in 1 Klick anlegbar + speicherbar; unvollständiger Agent
disabled+nicht kopierbar mit „fehlt: …"-Anzeige; vollständiger Agent
aktivier-/kopierbar. uv run pytest -q (test_agents_and_templates erweitern),
ruff, mypy; npm lint/tsc/test/build grün. Draft-PR.
```

### Agent C — Embed-Modus (Link vs. fest) + Resource→Resource

```
Branch: feat/embedding-mode-resource-compose

Kontext: Eingebettete Playbooks/Resources werden vom MCP-Server aktuell teils
VOLL inline mitgesendet (apps/mcp/.../server.py:226-231: link_scope=='resource'
→ ganzes Dokument in linked_resources). Es gibt KEIN Flag, das Link vs. fest
steuert. Resource→Resource-Komposition existiert backendseitig (Migration 0032,
resource_composition_service/repository, MCP fetch_resource:308 hängt
sub_resources als Pointer an); im Frontend ist SubResourcePicker gelistet —
PRÜFE, ob er in den ResourceEditor verdrahtet ist.

ZIEL 1 — Embed-Modus: Jede Einbettung (playbook→resource, resource→resource,
und falls vorhanden persona→playbook) bekommt einen Modus: STANDARD 'lazy'
(= nur als Link/Referenz, NICHT im MCP-Kontext mitgesendet — der Agent kann es
bei Bedarf via fetch nachladen) ODER 'inline' (= fest eingebettet, vom MCP
mitgesendet). Default überall 'lazy' (reduziert gesendeten Kontext; bewusst
breaking für bestehende resource-scope-Links — das ist gewollt). Der User kann
pro Einbettung im Editor auf 'inline' umschalten.

ZIEL 2 — Resource→Resource im UI: SubResourcePicker vollständig in den
ResourceEditor integrieren (Liste bestehender Sub-Resources, Hinzufügen via
Picker, Entfernen), inkl. des Embed-Modus-Toggles. Zyklus-Guard existiert
serverseitig.

AUFGABE:
- Migration 0040_link_embedding_mode.sql: Spalte embedding_mode TEXT NOT NULL
  DEFAULT 'lazy' CHECK in ('lazy','inline') auf playbook_resource_link.
- Migration 0041_composition_embedding_mode.sql: gleiche Spalte auf
  resource_composition (und persona_playbook-Link, falls existent).
- packages/models/resource.py + playbook.py + links.py: embedding_mode-Feld in
  den Link-Item/Read-Modellen ergänzen (Default 'lazy'). Barrel-Export pflegen.
- Repos set_links() (playbook_resource_link_repository, resource_composition_
  repository): embedding_mode schreiben/lesen.
- apps/mcp/server.py: inline NUR noch bei embedding_mode=='inline'; lazy-Links
  bleiben reine Pointer (id/name/fetch_call/preview).
- Frontend: ResourceBlockLinkPicker (playbooks-Feature) + SubResource-Integration
  (resources-Feature): pro Link ein Modus-Toggle „Link (lazy)" / „Fest einbetten".

RESERVIERTE Migrationsnummern für DICH: 0040, 0041. Nimm keine andere.
NUR anfassen: oben genannte Models/Repos/MCP + apps/web/.../features/resources/**
und features/playbooks/** (nur Link/Compose-Komponenten). NICHT features/agents,
dashboard, personas-Editor anfassen. NICHT version_status.py.

DoD: lazy-Link wird vom MCP NICHT inline gesendet, inline schon; Toggle im UI
funktioniert; Sub-Resources im ResourceEditor anleg-/entfernbar. uv run pytest -q
(test_playbook_resources, test_resource_composition erweitern + MCP-Test), ruff,
mypy; npm lint/tsc/test/build grün. Draft-PR mit Hinweis auf das bewusste
Breaking-Behavior (Default lazy).
```

## Welle 2 — i18n (nach Merge von A/B/C)

### Agent D1 — i18n der Oberfläche (DE/EN)

```
Branch: feat/i18n-ui

Kontext: Es gibt KEINE i18n-Infrastruktur. ~390 hartkodierte deutsche Strings in
apps/web/src/features/**, app/routes.tsx, components/{layout,data}. Tailwind v4,
shadcn-Primitives, react-router-dom@7.

AUFGABE:
- react-i18next (+ i18next, i18next-browser-languagedetector) einrichten:
  i18n-Init, Provider in der App-Wurzel, Namespaces pro Feature.
- locales/de.json + locales/en.json. ALLE sichtbaren Strings (title, label,
  description, placeholder, aria-label) auf t('key') umstellen — feature-weise
  durchgehen.
- Sprachumschalter in AppShell/Settings (shadcn-Primitive, kein <button>).
  User-Präferenz persistieren (Supabase user_metadata 'preferred_locale' ODER
  Settings-Endpoint — wähle den einfachsten konsistenten Weg, dokumentiere ihn).
- Locale beim API-Client mitgeben (Accept-Language / ?locale=), damit Content-
  Sprache (D2) gezogen werden kann — KOORDINIERE das Locale-Plumbing mit D2.

NUR Frontend + ggf. minimaler User-Pref-Persist. KEINE *_version-Migrationen,
KEINE MCP-Änderung (das macht D2). Rebase auf main (nach Welle 1).

DoD: Komplette UI auf DE und EN umschaltbar, keine sichtbaren Hardcoded-Strings
mehr in features/**. npm lint/tsc/test/build grün. Lint-Gate „keine direkten
<button>/<a>" beachten. Draft-PR.
```

### Agent D2 — Mehrsprachige Inhalte (Agents/Personas/Playbooks/Resources)

```
Branch: feat/i18n-content-model

Kontext: Persona/Playbook/Resource sind versioniert (*_version-Tabellen,
content::jsonb). KEIN locale-Feld. placeholders/registry.py kennt schon
locale="de-DE". MCP-Tools (apps/mcp/server.py) liefern Inhalte ohne Sprach-Param.
Migrationen stehen bei 0041 nach Welle 1.

SCHRITT 0 (PFLICHT): Schreibe zuerst einen kurzen ADR/Plan unter .claude/plan/
bzw. docs/adr/ zum Content-i18n-Modell und lege eine Stop-Marke für Review ein,
BEVOR du die DB-Migration ausführst. Vorgeschlagenes Modell: locale-Spalte
('de'|'en', Default 'de') auf persona_version/playbook_version/resource_version
(+ system_prompt_template_version), Unique-Constraints um locale erweitern. Beim
Initialisieren wählt der User eine/mehrere Sprachen → die entsprechenden
Sprachvarianten werden angelegt. Bestehende Daten = implizit 'de'.

AUFGABE (nach ADR-Freigabe):
- Migration ab 0042: locale-Spalten + angepasste Unique-Indizes.
- packages/models: locale in den Version-Modellen; Create-/Init-Logik für
  mehrere Sprachvarianten.
- Services: beim Anlegen Sprachvariante(n) gemäß User-Auswahl erzeugen.
- API-Router (personas/playbooks/resources): ?locale=-Param beim Lesen.
- MCP get_persona/fetch_playbook/fetch_resource/list_*: locale-Param, Default
  'de' (Backward-Compat). Filtert weiterhin status='active'.
- Frontend Create-Flows: Sprach-Auswahl beim Initialisieren. Locale-Plumbing
  mit D1 abstimmen.

RESERVIERTE Migrationsnummern: ab 0042 aufsteigend. Rebase auf main (nach Welle 1).
KEINE UI-String-Extraktion (das ist D1).

DoD: Persona/Playbook/Resource in DE+EN anlegbar; API + MCP liefern korrekte
Sprachvariante per locale; Default 'de' unverändert. uv pytest/ruff/mypy +
npm-Gates grün. Draft-PR mit verlinktem ADR.
```

## Offene Risiken / Notizen

- **D2 ist eine Einbahnstraße** (DB-Modell) → ADR-Freigabe vor Migration zwingend.
- Default `lazy` in Stream C ist ein **bewusstes MCP-Breaking-Behavior** für
  bestehende resource-scope-Links (vom User gewünscht: Kontext reduzieren).
- `SubResourcePicker` evtl. schon vorhanden → Stream C verifiziert Verdrahtung,
  statt neu zu bauen.
