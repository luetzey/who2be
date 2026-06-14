# Welle 4 — Forms „alles auf einer Seite" (#4)

Phase-3 Runde 3, Welle 4. Vorgaenger: PR #76 (Welle 1+3). Branch: `feat/phase-3-round3-wave4`.

## Ziel (User-Vorgabe)

> „Voller Editor, Anlegen geht immer, aber wenn etwas fehlt dann nicht aktiv oder review schalten muss in draft bleiben."

- Anlege-Seite zeigt **dieselbe Form** wie die Detail-Seite (BlockNote-Body,
  alle Properties, Tags, etc.) — keine Zwei-Stufen-Logik mehr.
- **Create ist immer erlaubt** mit nur `name` als Pflichtfeld.
  Body/Beschreibung/Tags duerfen leer sein → Result-Version landet im
  `status='draft'`.
- **Promote (draft → review / draft → active)** blockt mit klarer
  Fehlermeldung, wenn Pflichtfelder fehlen. Die Liste der Pflichtfelder ist
  pro Entity definiert (siehe unten).

## Scope

In Welle 4 betroffen: Persona, Resource, Agent. (Playbook ist durch Welle 3
bereits auf dem Ziel-Stand.) Cluster E (Slash-Templates fuer Agent-Body)
laeuft separat in Welle 5.

## Pflichtfeld-Definition pro Entity

| Entity   | Pflichtfelder fuer `draft → review/active` |
|----------|--------------------------------------------|
| Persona  | `name`, `description`, `body` (nicht leer) |
| Playbook | `name`, `description`, `body`, `type`      |
| Resource | `name`, `description`, `body`              |
| Agent    | `name`, `persona_id`, `system_prompt_template_id` |

(Tags, Triggers, Properties bleiben optional.)

## Vertrag: 409-Response bei Promote-Validation-Fail

`POST /v1/workspaces/{ws}/{entity}/{id}/versions/{v}/transition` mit
unzureichenden Pflichtfeldern:

```http
HTTP/1.1 409 Conflict
Content-Type: application/problem+json

{
  "type": "https://who2be.dev/errors/promote-validation-failed",
  "title": "Promote nicht moeglich: Pflichtfelder fehlen",
  "status": 409,
  "detail": "Pflichtfelder muessen vor Promote ausgefuellt sein.",
  "missing": ["description", "body"]
}
```

- `missing` enthaelt die internen Feldnamen aus der Tabelle oben.
- Status **409** (nicht 422), weil es ein Status-Konflikt ist und nicht eine
  syntaktisch ungueltige Eingabe (Drafts ohne Body sind legitim).
- Existierende Transition-Fehler (z. B. „Bereits aktiv") bleiben unveraendert
  bei ihren bisherigen Status-Codes.

## Backend-Aenderungen

- `packages/models/who2be_models/persona.py` (bzw. wo `PersonaCreateInput`
  lebt) — Pflichtfeld-Validatoren auf `name` reduzieren, Rest optional /
  leerstring-erlaubt. Gleiches fuer Playbook (Welle 3 hat schon teilweise
  vorbereitet — verifizieren) / Resource / Agent.
- `apps/api/src/who2be_api/services/version_transition_service.py` (oder
  Aequivalent) — neuer Step `validate_promote_requirements(version, entity)`
  vor dem Status-Wechsel. Wirft `PromoteValidationError(missing=[...])`.
- `apps/api/src/who2be_api/routers/{personas,playbooks,resources,agents}.py`
  — Transition-Endpunkt faengt `PromoteValidationError` und liefert obige
  `application/problem+json`-Response.
- Tests: Create-Endpunkt mit minimalen Daten 201; Transition mit
  unvollstaendigem Draft 409 mit korrekter `missing`-Liste; Transition mit
  vollstaendigem Draft 200.

## Frontend-Aenderungen

- `PersonaEditorForm` analog zu `PlaybookEditorForm` um optionale
  `onSubmit`/`actions`-Slots erweitern (das Muster ist in PR #76 etabliert,
  Datei `apps/web/src/features/playbooks/components/PlaybookEditorForm.tsx`).
- `useCreatePersona` auf gleiches Schema wie `usePersonaForm` heben
  (`bodyBlocks`, Properties-Array, ...). NewPage rendert `PersonaEditorForm`
  mit Submit-Button.
- Resource: vermutlich kein separater `ResourceEditorForm` heute — pruefen.
  Wenn die ganze Editor-Logik in `ResourceDetailPage.tsx` inline liegt, eine
  `ResourceEditorForm`-Komponente extrahieren, dann beide Seiten nutzen sie.
- `AgentNewPage` ist heute schon naeher am Ziel — verifizieren, dass alle
  Felder (Persona, Systemprompt-Template, Settings) auf einer Seite sind. Falls
  ja, hier nichts tun. **Hinweis:** Der Systemprompt-Body wandert in Welle 5
  auf BlockNote — also jetzt KEINEN BlockNote-Umstieg fuer Agents bauen.
- `StatusActionBar` (alle drei Entities): 409-Response mit `missing`-Array
  parsen und unter dem Promote-Button anzeigen
  („Vor dem Aktivieren ausfuellen: Beschreibung, Body").

## Validierung bei Welle-4-Ende

- Anlegen ohne Body in allen vier Entities → 201, Version sitzt auf `draft`.
- Promote-Button auf einer unvollstaendigen Version → Inline-Fehlertext mit
  konkreten Feldnamen, Button NICHT disabled (Feedback muss aktiv ankommen).
- Promote nach Ausfuellen → erfolgreich, Version aktiv.

## Agenten-Plan

Zwei parallele Worktree-Subagents (beide Sonnet):

- **Backend-Agent:** Schema-Lockerung, Transition-Validator,
  `application/problem+json`-Response, Tests.
- **Frontend-Agent:** PersonaEditorForm/Slots + Create-Hook + NewPage,
  Resource-Extract + NewPage, AgentNewPage-Audit, StatusActionBar-Hardening
  (alle drei Entities), Tests.

Beide branchen von `feat/phase-3-round3-wave4`. Integration durch mich am
Ende (Merge + Sammel-Test + Stack-Rebuild fuer User-Smoke).
