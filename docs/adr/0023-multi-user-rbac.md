# ADR-0023 — Multi-User-RBAC pro Workspace + Token-Role-Snapshot

- Status: Akzeptiert
- Datum: 2026-05-29
- Kontext: Who2Be Phase 2.3 — Multi-User pro Workspace

## Kontext

ADR-0019 hat die Tenant-Hierarchie eingefuehrt (`User → org_member →
organization → workspace → Entity`) und `workspace_member` bereits befuellt,
aber noch nicht ausgewertet: jeder Member darf heute faktisch alles. ADR-0020
hat den Status-Workflow pro Version festgezurrt (Draft/Review/Active/Inactive)
und in §Konsequenzen offengelassen, dass Phase 2.3 "oben drauf nur noch RBAC
nachreicht: Editor darf `draft → review`, Admin darf `review → active`".

Phase 2.3 macht daraus echte Autorisierung. Damit das geordnet passiert,
trennen wir Schema/Modelle (diese Stufe, Phase 2.3-0) von Enforcement und UI
(spaetere Stufen). Diese ADR haelt die Rollen-Semantik, die Permission-Matrix
und den Token-Role-Snapshot fest — der Code (geschaerfte
`get_current_workspace`, Member-/Invitation-Endpoints, Frontend) folgt
darauf aufbauend.

Plan-Vorlage: `.claude/plan/2026-05-27-1921_phase-2-vollwertige-app.md`,
§2.3.A / §2.3.B. Schema-Anteil dieser Stufe:
`0017_workspace_invitation.sql`, `0018_api_token_role_snapshot.sql`.

## Optionen

- **A — Flache Rollen (`member` vs. `admin`).** Nur zwei Stufen. Einfach,
  aber kann "darf lesen, aber nicht schreiben" (Viewer) nicht abbilden und
  kollabiert Reviewer- und Verwaltungsrechte in eine Rolle.
- **B — Dreistufige Hierarchie `admin > editor > viewer` (gewaehlt).**
  Deckt Read-only (viewer), inhaltliche Arbeit (editor) und
  Review/Verwaltung (admin) ab. Spiegelt die DB-CHECK-Constraints aus
  `workspace_member` (0007) und `workspace_invitation` (0017).
- **C — Frei konfigurierbare Permissions pro User.** Maximale Flexibilitaet,
  aber massiver Mehraufwand (Permission-Tabelle, UI, Audit) — fuer den
  aktuellen Funktionsumfang Over-Engineering.

Fuer den Token-Rollenbezug:

- **T1 — Token erbt dynamisch die aktuelle Rolle des Erstellers.** Token-
  Rechte folgen Live-Aenderungen der Member-Rolle. Bequem, aber
  Privilege-Drift: ein zum Admin promoteter User hebt damit unbemerkt die
  Rechte all seiner alten Token an.
- **T2 — Token pinnt die Rolle als Snapshot (gewaehlt).** Token traegt
  `role` (Spalte aus 0018), gesetzt beim Erstellen aus der damaligen Rolle
  des Erstellers; spaetere Rollenwechsel des Users aendern das Token nicht.

## Entscheidung

**Option B + T2.**

### Rollen-Hierarchie

`admin > editor > viewer`. Single-Source ist `WorkspaceRole` (StrEnum) in
`packages/models/src/who2be_models/workspace_member.py`; die DB spiegelt sie
als CHECK-Constraint (`workspace_member.role`, `workspace_invitation.role`,
`api_token.role`).

### Permission-Matrix

| Aktion | viewer | editor | admin |
|---|:---:|:---:|:---:|
| Personas/Playbooks/Resources **lesen** (alle Stati) | ✅ | ✅ | ✅ |
| Draft **erstellen** (`PUT` ⇒ neue Draft-Version) | ❌ | ✅ | ✅ |
| Draft **editieren** | ❌ | ✅ | ✅ |
| Draft/Entity **loeschen** | ❌ | ✅ | ✅ |
| Transition `draft → review` (Submit for Review) | ❌ | ✅ | ✅ |
| Transition `review → draft` (Bounce zurueck) | ❌ | ✅ | ✅ |
| Transition `review → active` (**Promote to Active**) | ❌ | ❌ | ✅ |
| Transition `active → inactive` (Retire) | ❌ | ❌ | ✅ |
| Token **erstellen/listen/widerrufen** (eigener Scope) | ❌ | ✅ | ✅ |
| **Member** listen | ✅ | ✅ | ✅ |
| Member **einladen / Rolle aendern / entfernen** | ❌ | ❌ | ✅ |

Leitlinien hinter der Matrix:

- **viewer = read-only.** Keine Mutation, kein Token, keine Verwaltung — aber
  voller Lesezugriff inkl. Drafts/Reviews (Transparenz im Team).
- **editor = inhaltliche Arbeit.** Darf Inhalte erstellen, editieren und in
  Review schieben, aber **nicht** selbst nach `active` promoten. Damit gibt es
  ein echtes Vier-Augen-Prinzip: der Editor schreibt, der Admin gibt frei.
- **admin = Reviewer + Verwaltung.** Die einzige Rolle mit
  Promote-to-Active (Reviewer-Rolle aus ADR-0020) und mit Member-/
  Invitation-Verwaltung.

`active → inactive` (Retire einer Live-Version) ist eine inhaltliche
Freigabe-Entscheidung und bleibt deshalb admin-only, konsistent mit
Promote-to-Active.

### Abgrenzung: Org-Rolle vs. Workspace-Rolle

**Die Matrix oben gilt fuer Workspace-Rollen.** `org_member.role`
(`owner` / `admin` / `member`, eingefuehrt in ADR-0019) traegt **keine** Rechte
bei der Anlage eines Workspace: `POST /v1/organizations/{id}/workspaces` prueft
die Mitgliedschaft in der Organisation, aber keine Mindestrolle — jedes
Org-Mitglied darf Workspaces anlegen.

Das ist **Absicht**, nachgetragen am 2026-09-08 (Issue #481, Befund
F-Phase2-04 in `docs/security-findings-phase-2.md` §9). Eine Organisation ist
als kollaborativer Raum gedacht; wer darin ist, darf darin arbeiten. Die
Strenge sitzt eine Ebene tiefer, dort wo Inhalte entstehen und freigegeben
werden — genau die Ebene, die diese Matrix beschreibt.

Die Asymmetrie ist damit benannt statt versehentlich: *innerhalb* eines
Workspace ist die Rollenpruefung streng (`require_role`, seit #469 mit
aal2-Gate fuer admin-Token), auf Org-Ebene beim Anlegen gibt es sie nicht.

**Wer das aendern will, aendert einen Vertrag, keinen Bug.** Eine Mindestrolle
auf Org-Ebene waere ein **Breaking Change** fuer Betreiber, deren `member`
heute Workspaces anlegt, und braucht deshalb eine eigene Entscheidung mit
Migrationshinweis — nicht den Nebeneffekt eines Review-Funds.

### Promote-to-Active = admin-only

Der `transition`-Endpoint pro Entity-Typ prueft die Zielstufe gegen die
Rolle: `review → active` und `active → inactive` verlangen `admin`. Alle
uebrigen erlaubten Uebergaenge (`is_allowed_transition` aus ADR-0020) sind ab
`editor` zulaessig. Die State-Machine selbst bleibt unveraendert — RBAC ist
eine zusaetzliche Schicht davor, kein Umbau.

### Token-Role-Snapshot

`api_token` bekommt eine `role`-Spalte (`0018`,
`CHECK (role IN ('admin','editor','viewer')) NOT NULL DEFAULT 'admin'`).

- **Pinning beim Erstellen:** `TokenCreate.role` ist optional; `None` ⇒ der
  Service setzt die aktuelle Workspace-Rolle des Erstellers als Snapshot. Ein
  explizit gesetzter Wert darf die Ersteller-Rolle **nicht uebersteigen** (ein
  editor kann kein admin-Token erzeugen) — geprueft im Service.
- **Statisch bei Nutzung:** Bei Token-Auth gilt die gepinnte Snapshot-Rolle,
  **nicht** die aktuelle Rolle des Erstellers.
- **Backfill:** Bestands-Token (Single-User-MVP) bekommen per DEFAULT
  `admin` und bleiben damit funktional unveraendert — bestehende Tests
  bleiben gruen.

**Trade-off (begruendet).** Der Snapshot verhindert *Privilege-Drift nach
oben*: wird ein User spaeter zum admin promotet, erben seine alten Token
**nicht** automatisch admin-Rechte. Die Kehrseite: wird ein User
*herabgestuft* (admin → editor) oder ganz entfernt, behaelt ein vorher
erstelltes admin-Token seine Rechte, bis es **explizit revoked** wird. Wir
nehmen das bewusst in Kauf — die Alternative (dynamische Bindung, T1) macht
Token-Rechte unvorhersehbar und an Live-Rollenwechsel gekoppelt, was im
Agenten-Kontext (langlebige, unbeaufsichtigte Token) gefaehrlicher ist als
ein vergessener Revoke. Mitigation: Member-Downgrade/-Removal **muss** im UI
und in der Doku den Hinweis "bestehende Token dieses Users widerrufen"
fuehren; ein spaeterer Schritt kann Downgrade optional mit Auto-Revoke der
betroffenen Token koppeln.

### Invitations

`workspace_invitation` (`0017`) traegt den Token **nur als Hash**
(ADR-0006-Linie, analog `api_token.token_hash`); der Klartext geht per Mail
raus und taucht serverseitig nur im Accept-Request auf (`InvitationAccept`).
`InvitationRead` gibt weder Hash noch Klartext zurueck. Schutzmechanismen:

- **Single-Use:** `accepted_at` markiert eine eingeloeste Einladung; ein
  zweites Accept mit demselben Token wird abgelehnt.
- **Expiry:** `expires_at` ist Pflicht; abgelaufene Token sind ungueltig.
- **Replay/Doppel-Invite:** partial unique Index
  `(workspace_id, lower(email)) WHERE accepted_at IS NULL AND revoked_at IS
  NULL` — max. eine offene Einladung je Mail und Workspace.
- **Revoke:** `revoked_at` entwertet eine offene Einladung und gibt den
  Slot fuer eine neue frei.

### Modelle (Phase 2.3-0, diese Stufe)

- `WorkspaceRole` StrEnum + `WorkspaceMemberRead` + `WorkspaceMemberUpdate`
  (nur `role`).
- `InvitationCreate` (email, role), `InvitationRead`
  (id, email, role, expires_at, created_at), `InvitationAccept` (token).
- `TokenRead` bekommt `role: WorkspaceRole`; `TokenCreate` bekommt optionales
  `role` (Default `None` ⇒ Snapshot der Ersteller-Rolle).

## Konsequenzen

- API-Kontrakt aendert sich additiv: `TokenRead.role` ist neu, aber alle
  Bestands-Token sind `admin` (Backfill-Default) — kein Verhaltenswechsel
  fuer existierende Clients.
- Diese Stufe ist **Schema + Modelle + ADR only**. Bewusst nicht enthalten:
  geschaerfte `get_current_workspace`, Member-/Invitation-Endpoints,
  Service-Logik fuer das Snapshot-Defaulting, Frontend und Mail-Versand —
  sie folgen in spaeteren Phase-2.3-Stufen und stuetzen sich auf diese ADR.
- `security-reviewer` prueft beim Enforcement-Schritt: Viewer kann keine
  Mutation ausloesen, Editor kann nicht nach `active` promoten,
  Invite-Token sind single-use + expiry, und kein Endpoint umgeht die
  Token-Snapshot-Rolle.
- Roll-Back ist billig: `workspace_invitation` droppen und
  `api_token.role` droppen — Bestandsdaten (Token, Member) bleiben
  unangetastet.

## Nachtrag 2026-10-22 — Rollenwechsel und Entfernen widerrufen Tokens

Der im Trade-off oben als "spaeterer Schritt" offengelassene Auto-Revoke ist
seit 951a088c (2026-07-22) umgesetzt, und zwar fuer **jeden** Rollenwechsel
(nicht nur Downgrade) und fuer das Entfernen eines Mitglieds. Die
Kehrseite "herabgestuftes Mitglied behaelt sein admin-Token" entfaellt damit;
die Snapshot-Semantik selbst (Pinning beim Erstellen, statisch bei Nutzung)
gilt unveraendert. Massgeblich ist der Code:
`WorkspaceMemberService.update_role` / `.remove` →
`TokenRepository.revoke_by_owner`, belegt durch
`apps/api/tests/test_tokens.py::test_member_downgrade_revokes_their_tokens`.
Die Mitglieder-Seite meldet den Widerruf nach jedem Rollenwechsel
(`members.list.tokensRevokedInfo`).

## Nachtrag 2026-10-24 — viewer über den OAuth-Connector

Owner-Entscheidung vom 2026-10-24 (Option A, Kanban-Karte t_b36bf77f): Ein
`viewer` darf einen Agenten über den OAuth-Connector **nutzen**. Das ist der
Weg „Kollegen nur nutzen lassen“. Die Leitlinie „viewer = read-only“ oben
gilt für Inhalte, Versionen, Tokens und Verwaltung unverändert. Über den
Connector kommen zwei Ausnahmen dazu, die bewusst gewollt sind:

- **Lesen inklusive Agentengedächtnis.** `search_memory` und `list_memories`
  liefern dem `viewer` auch Einträge mit `scope='agent'`. Ohne sie arbeitet
  der Agent beim Kollegen schlechter als beim Editor, und das Gedächtnis ist
  Teil dessen, was der Agent zur Nutzung braucht.
- **Gedächtnis-Vorschläge.** `save_memory` und `propose_memory_change` legen
  auch für einen `viewer` einen Eintrag bzw. Vorschlag an. Unter
  `memory_mode=suggest` ist er `pending` und wirkt erst nach menschlicher
  Freigabe. Agentengedächtnis gibt ein `editor` oder `admin` frei, das eigene
  Nutzergedächtnis die Person selbst (ADR-0053 3.1.1, 3.1.4). Das ist
  dieselbe Linie wie „Fall melden ab `viewer`“ (ADR-0053 F-W4): Der Kollege
  darf fürs Agentengedächtnis etwas vorschlagen, entscheiden darf er nicht. Unter
  `memory_mode=auto` gelten die Automatik-Zellen, die ein `admin`
  eingeschaltet hat, unabhängig von der Rolle des Nutzers am Connector
  (`memory_service.decide_memory_status`). Die Freigabe hat dann der Admin
  vorab erteilt.
- `record_usage` (Telemetrie) und `report_case` laufen wie bisher ab `viewer`.

Alles andere bleibt verboten. Der Connector-Token trägt die Rolle `viewer`,
ohne Anhebung. Schreibwerkzeuge (`update_agent`, `create_playbook`,
`create_persona`, `submit_feedback` …) stehen beim agent-gebundenen Token in
`tools/list`, weil der Filter dort der Agent-Policy folgt und nicht der Rolle.
Sie enden aber serverseitig mit `insufficient_role` und ohne Wirkung.

**Offen benannte Abweichung, nicht angeglichen:** Über REST ist das
Agentengedächtnis für einen `viewer` unsichtbar (`GET /memories` ohne
`scope='agent'`, `GET /memories/{id}` → `404 memory_not_found`, ADR-0053
6.4.1). Über MCP sieht derselbe `viewer` es. Begründung: In der Web-Oberfläche
verwaltet man das Gedächtnis, und das ist Editor-Arbeit. Über den Connector
nutzt man den Agenten. Wer das angleichen will, ändert einen Vertrag und
braucht eine eigene Entscheidung.

Beleg: `apps/api/tests/test_viewer_connector.py::test_viewer_nutzt_agent_per_connector_aendert_aber_nichts`
(voller DCR → authorize → consent → token, danach echte MCP-Aufrufe).
