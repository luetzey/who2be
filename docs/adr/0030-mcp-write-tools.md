# ADR-0030 — MCP-Write-Tools fuer die Kernelemente

- Status: Accepted
- Datum: 2026-06-05
- Kontext: Self-Refinement-Use-Case; Multi-User-Hosting mit RBAC aktiv
- Bezug: ADR-0005 (MCP als HTTP-Client), ADR-0023 (Token-Snapshot-Rolle),
  ADR-0012 (Write-Tools deferred — durch diese ADR superseded)

## Kontext

ADR-0012 hatte MCP-Write-Tools bewusst aus dem MVP herausgehalten und zwei
Re-Evaluation-Trigger benannt: (1) ein Self-Refinement-Use-Case (Agent soll
eigene Versionen vorschlagen) und (2) aktiviertes Multi-User-Hosting mit
Owner-Scoping und rollenbasiertem Zugriff. Beide Trigger sind erfuellt:

- Phase 2.3 hat RBAC eingefuehrt (`admin > editor > viewer`, `require_role`-Gate
  auf allen Mutating-Endpunkten) und API-Tokens tragen eine Snapshot-Rolle
  (ADR-0023).
- Der Versions-Workflow (`draft → review → active → inactive`, ADR-0020) ist die
  bereits existierende Approval-Schicht: ein Agent kann nur eine **Draft**
  erzeugen, das Scharfschalten (`→ active`) ist eine eigene, rollengeschuetzte
  Transition.

Damit existiert die in ADR-0012 geforderte Approval-/Audit-Infrastruktur, und
Write-Tools koennen verantwortbar exponiert werden.

## Entscheidung

Der MCP-Server exponiert **Write-Tools fuer die vier Kernelemente** (Persona,
Playbook, Resource, Agent), mit folgenden Grenzen:

- **Operationen:** create, update, Versions-Transition, restore und das Setzen
  der Verknuepfungen (Persona↔Playbooks, Playbook↔Resource-Links,
  Playbook-Composition, Resource-Sub-Resources). **Kein** Loeschen ueber MCP
  (delete bleibt Web-UI / direktem REST vorbehalten).
- **Duenner Adapter (ADR-0005):** Die Tools tragen keine Geschaeftslogik und
  keine Berechtigungspruefung. Autorisierung, Owner-Scoping und der
  Status-Workflow werden ausschliesslich serverseitig in der REST-API
  durchgesetzt. Der MCP-Layer reicht 401/403/409/422 als `ToolError` durch.
- **Berechtigung (ADR-0023):** Schreiben erfordert einen API-Token mit
  mindestens `editor`-Rolle; Status-Promote (`→ active`) und Retire
  (`active → inactive`) erfordern `admin`. Ein `viewer`-Token kann weiterhin
  nur lesen.

## Persistence-Layer-Injection (das ADR-0012-Kernrisiko)

ADR-0012 nannte den zentralen Einwand: ein Agent-Write-Pfad ist ein
Prompt-Injection-Vektor, der ueber eine veraenderte Persona/Playbook spaeter
wieder gelesen wird. Dieser Einwand wird so adressiert:

- **MCP-Reads sehen nur `status='active'`.** Ein Agent-Write landet als `draft`
  (Default-Draft, ADR-0020) und ist fuer Lese-Tools **unsichtbar**, bis eine
  Transition nach `active` erfolgt.
- **Die Promote-Transition ist rollengeschuetzt** (`admin`). Ein reiner
  `editor`-Token kann Inhalte vorschlagen, aber nicht selbst scharfschalten —
  der Approval-Schritt bleibt eine bewusste, hoeher privilegierte Handlung.
- **Audit:** `created_by` pro Version plus die Status-Historie
  (`status_history`, "warum aktiv") bilden die Schreib-Spur ab.

Wer einem Agenten einen `admin`-Token gibt, hebt diese Grenze bewusst auf —
das ist eine Deployment-Entscheidung, keine Eigenschaft der Tools.

## Konsequenzen

- `apps/mcp/src/who2be_mcp/server.py` ist nicht mehr Read-only; neue Write-Tools
  spiegeln 1:1 die vorhandenen REST-Mutationen.
- `apps/mcp/src/who2be_mcp/client.py` erhaelt einen `_write`-Pfad
  (`_request`/`_raise_for_status` mit `_get` geteilt), inkl. Mapping von
  403/409/422 auf agenten-lesbare `ToolError`s.
- Kein neuer Audit-Layer noetig — der bestehende `created_by`/`status_history`-
  Mechanismus deckt MCP-Writes ab (gleiche REST-Endpunkte wie die Web-UI).
- Empfehlung fuer Agent-Deployments: einen `editor`-Token ausgeben, wenn der
  Agent vorschlagen, aber nicht selbst veroeffentlichen soll.
