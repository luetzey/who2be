# ADR-0043 — Externe Tools als versionierte Workspace-Aggregate mit stabiler Alias-Referenz

- Status: Accepted
- Datum: 2026-07-18
- Kontext: ADR-0025/0040 (Placeholder-Registry, Fetch-Time-Rendering), ADR-0042
  (SSoT-Mapping fuer MCP-Tools), Issue WP-6
- Plan: `.claude/plan/2026-07-18-1315_external-tools-tool-ref.md`

## Kontext

Heute fehlt ein zentraler Ort fuer die Verwaltung von MCP-Server-Bindungen
(z. B. Todoist, Things 3, Kalender) in einem Workspace. Tool-Anweisungen werden
als Freitext in Playbooks/Personas dupliziert; ein Wechsel des konkreten Tools
(z. B. Todoist → Things 3) erfordert N manuelle Edits mit Drift-Risiko.

Die bestehende Placeholder-Architektur (ADR-0025/0040, Fetch-Time-Rendering)
liefert bereits die Semantik „einmal aendern, ueberall aktuell" — es fehlt nur
die Ziel-Entitaet (ein versioniertes Aggregat fuer externe Tools) und ein
Resolver fuer den neuen Placeholder-Typ `tool-ref`.

## Entscheidung

1. **Entitaet: `external_tool`** — eigenes versioniertes Workspace-Aggregat
   (analog persona/playbook/resource). Tabellen `external_tool` (Zeile pro
   Workspace/Alias) + `external_tool_version` (Inhalt, Status-Workflow). Alias
   lebt auf der Aggregat-Zeile mit partiellem UNIQUE-Index
   `(workspace_id, alias)` — stabile Identitaet ueber Versionen hinweg.

2. **Ausbaustufe B: rein instruktiv** — das Aggregat haelt nur beschreibende
   Daten (display_name, mcp_server_name, tool_names, usage_notes,
   fallback_note), **keine** Server-URLs oder Credentials. Ein echter MCP-
   Gateway/Proxy (Ausbaustufe C) ist explizit **nicht** Teil dieses ADR;
   Ausbaupfad dokumentiert unten.

3. **Placeholder-Art: `tool-ref`** — Pills referenzieren Alias statt UUID
   (z. B. target_id=`todo`). Resolver sucht die aktive Version des Tools mit
   jenem Alias im Workspace und expandiert zu einem Anweisungs-Block; kein
   aktives Tool → Miss (`unresolved_key`, wie playbook/resource-Resolver).

4. **Einsatzorte: alle Body-Rendering-Pfade** — System-Prompt-Vorlagen,
   Persona-, Playbook-, Resource-Bodies. Resource-Editor rendert Pills
   bauartbedingt nicht (kein `render_template_body`), daher dort
   pill-loseFallback-Prosa.

5. **MCP-Exposure: Read + Write** — neue Tools `list_external_tools`,
   `get_external_tool(alias)` (Read-Scope-gefiltert), `create/update/
   transition/restore_external_tool` (capability `external_tool_write`,
   Default aus). Neue Domain `external_tool` in Read-Scopes (Default all,
   JSONB-abwaertskompatibel).

## Alternativen

### A) Resource-Konvention (verworfen)

Externe Tools als spezialisierte Resources mit Tags (z. B. `tool:todo`) statt
eigenstaendiges Aggregat.

**Ablehnung:** (1) Semantisches Noise — Resources dienen dem Wissen/Kontext
eines Playbooks, nicht der Extern-Tool-Registry. (2) Keine dedizierte Policy-
Domain (read_scope `resource` ist zu breit). (3) Keine Unterscheidung in MCP-
Discovery (`list_resources` haette den vollen Response, nicht gezielt `list_
external_tools`). (4) Alias-Eindeutigkeit wäre Tag-Konvention ohne DB-Zwang.

### C) MCP-Gateway/Proxy (vertagt, Ausbaupfad dokumentiert)

Who2Be wird selbst zum MCP-Gateway: ein Server ruft beim Agenten an; der Agent
nutzt Tool-Namen direkt aus `external_tool.tool_names`, Who2Be routet an den
echten MCP-Server.

**Ablehnung für v1:**
- Credentials-/URL-Storage nötig → neue Security-Oberfläche ohne Mehrwert
  für den instruktiven Anwendungsfall (Agent erhält Anweisung, nicht Call
  Forwarding).
- Laufzeit-Verbindungsprüfung (ist der Server da?) führt zu Timeouts im
  Rendering.
- Keine neuen Agent-Fähigkeiten relativ zur Anweisung im Prompt — nur
  Komplexität.

**Ausbaupfad (v1.1+):**  
Der Alias wird dann zum Proxy-Namespace; `external_tool` speichert zusätzlich
URL/Credentials; ein "Gateway-Modus" delegiert Tool-Calls an den echten
Server. Architektur-Vorbereitung im ADR.

## Konsequenzen

- **CRUD + Status-Workflow:** Das neue Aggregat folgt dem persona/resource-
  Muster vollständig — draft→review→active→inactive, Versionierung,
  Export, GDPR-Purge (Kaskaden-Delete auf FK).

- **ALIAS-Eindeutigkeit pro Workspace:** 409 bei Konflikt; Slug-Validierung
  (alphanumerisch, Bindestrich, Unterstrich, Länge 1–64).

- **Fetch-Time-Expansion:** Ein Agent mit Pills `{ kind: 'tool-ref', target_id:
  'todo' }` in seinen Playbooks/Persona/Prompt-Vorlage erhält bei jedem
  `fetch_agent` die jeweils aktive Bindung inline — keine Extra-Calls nötig,
  kein Re-Edit der Pills nötig bei Alias-Rebinding.

- **MCP-Tool-Liste:** 6 neue Tools (list/get/create/update/transition/
  restore), 54 Total im Mapping `who2be_models.tool_requirements` (ADR-0042).

- **Keine Feedback-Migration:** Feedback-Ziele um `entity_type=external_tool`
  erweitert (Schema-Entkopplung: kein DB-CHECK, nur Pydantic-Validierung).

- **Builder-Spielraum:** Agenten können (über MCP) externe Tools katalogisieren
  und in ihre Playbooks/Personas Pills einfügen; das ist der Start für eine
  Tool-Suggestion-Funktion (v1.1).

## Architektur-Vorbereitung (für Ausbaupfad C)

Damit ein später Gateway möglich ist, ohne APIs zu brechen:

1. Alias bleibt primäre ID in Pills (kein UUID-Hardcoding).
2. `external_tool_version.content` ist flexibel — Fields wie `server_url`,
   `auth_config`, `polling_interval` können später hinzukommen, JSONB-
   abwärtskompatibel.
3. Neues Feld `gateway_enabled: bool` könnte später sagen, ob die Runtime
   diesen Tool-Server proxen soll.
4. Tool-Namen aus `tool_names: list[str]` sind schon strukturiert (nicht
   Freitext).

Migrations-Path: keine bestehenden APIs brechen, nur graduell Neue hinzufügen.
