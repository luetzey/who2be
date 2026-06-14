# Plan: Who2Be — Vollwertige App (Phase 2.1 / 2.2 / 2.3)

**Status:** ✅ Alle drei Phasen abgeschlossen (2026-05-29). Sub-Pläne sind je
einzeln auf Done geflippt. ADR-Backlog 0019/0020/0021/0022/0023 abgelegt.

| Phase | PRs | Sub-Pläne |
|---|---|---|
| 2.1a — Tenancy + Schema-Lock | #38, #41, #42 | `…2.1a-1…`, `…2.1a-2…` |
| 2.1b — Status + Dashboard | #44, #46, #45, #47 | `…2.1b-0…`, `…2.1b-status-backend`, `…2.1b-dashboard-backend`, `…2.1b-status-dashboard-web` |
| 2.2 — Resources + BlockNote | #48 | `…2.2-resources-blocknote` |
| 2.3 — Multi-User RBAC | #49, #50, #51, #52 | `…2.3-0…`, `…2.3-A…`, `…2.3-B…`, `…2.3-C…` |

## Context

Der MVP ist code-seitig launch-bereit (Personas/Playbooks/Tokens CRUD, MCP-Read-Tools, Web-UI mit Auth). Um Who2Be zu einer **vollwertigen Multi-Tenant-App** zu machen, brauchen wir vier zusammenhaengende Bausteine: **Organization+Workspace-Hierarchie** (Mandantentrennung), **Status-Workflow pro Version** (Draft/Review/Active/Inactive), **Resources mit Block-Editor** (Notion-aehnliche Wissensebene, mit Playbook-Block-Refs) und ein **Dashboard** als Einstieg. Mehrere User pro Workspace ist die letzte Stufe — die Datenstruktur wird aber schon in Phase 2.1 darauf vorbereitet, damit Phase 2.3 ohne Migration auskommt.

Aufgeteilt in **3 sequenzielle Phasen**, jede pro sich shipable. Jede Phase laeuft hinter Feature-Branch + Migration-Files + neuem ADR-Eintrag.

## Architektur-Entscheidungen (bestaetigt)

| Entscheidung | Wahl |
|---|---|
| Tenant-Hierarchie | `User → org_member → Organization → Workspace → Entity` |
| API-Routing | Hard-Cut: `/v1/workspaces/{ws_id}/...` (kein v2-Parallelbetrieb) |
| Status-Lokation | **Pro Version**, mit DB-Invariante "max. je 1 Draft/Review/Active pro Entity" |
| Block-Refs | Immer auf `latest` (kein Version-Pin) |
| Editor | TipTap (low-level), Block-UI selbst auf shadcn/Tailwind |
| Token-Scope | Pro Workspace (Token traegt `workspace_id`) |
| Workspace-Switch | URL-Praefix `/w/{ws_id}/...`, Switcher links in AppShell |

---

## Phase 2.1 — Tenant-Layer + Status + Dashboard

**Ziel:** Multi-Tenant-Fundament. Bestehende Features (Persona/Playbook) leben kuenftig in einem Workspace, jede Version hat einen Status, Dashboard ist erster Einstieg nach Login.

### 2.1.A — Datenmodell

Neue Migrations-Files in `apps/api/src/who2be_api/migrations/`:

- `0005_organization.sql`
  - `organization(id, name, slug, created_at, kind enum('personal','company'))`
  - `org_member(org_id, user_id, role enum('owner','admin','member'), invited_by, joined_at)` — Composite-PK `(org_id, user_id)`
- `0006_workspace.sql`
  - `workspace(id, org_id, name, slug, created_at)`; Unique `(org_id, slug)`
- `0007_workspace_member.sql` (Tabelle existiert ab jetzt, aber wird in 2.1 nur fuer Owner befuellt; in 2.3 echt benutzt)
  - `workspace_member(workspace_id, user_id, role enum('admin','editor','viewer'), joined_at)`
- `0008_persona_workspace.sql` / `0009_playbook_workspace.sql` / `0010_api_token_workspace.sql`
  - `ALTER TABLE persona ADD COLUMN workspace_id UUID` (nullable zunaechst), Backfill, dann `NOT NULL` + FK + Index.
  - **Behalte `owner_id` als Audit-Spalte** (`created_by`) — bitter zu droppen, billig zu behalten.
  - Composite-FK auf `persona_playbook` umbauen: `(workspace_id, persona_id)` + `(workspace_id, playbook_id)` (gleiches Defense-in-Depth-Prinzip wie heute, siehe ADR aus `apps/api/src/who2be_api/migrations/0004_persona_playbook.sql`).
- `0011_status_on_versions.sql`
  - `ALTER TABLE persona_version ADD COLUMN status enum('draft','review','active','inactive')`
  - `ALTER TABLE playbook_version ADD COLUMN status ...`
  - **Partial Unique Index** pro Entity: `CREATE UNIQUE INDEX ... ON persona_version (persona_id) WHERE status='active'` — DB-erzwungene Invariante.
  - Analog je ein Index fuer `WHERE status='draft'` und `WHERE status='review'` — erzwingt "max. 1 Draft / 1 Review zur Zeit".
  - Backfill: aktuell `current_version` → `status='active'`, alle anderen → `status='inactive'`.
- `0012_status_history.sql`
  - `status_history(entity_type, entity_id, from_status, to_status, changed_by, changed_at, note)` — append-only Audit, **separat** vom Version-Bump (Status-Wechsel bumpt **keine** Version).

### 2.1.B — Backfill-Migration (einmalig)

Im selben `0008`-File oder als separates `0013_backfill_tenants.sql`:

1. Pro existierendem `owner_id` (= distinct ueber `persona.owner_id ∪ playbook.owner_id ∪ api_token.owner_id`): Personal-`organization` (kind='personal') + `org_member` als `owner` + Default-`workspace` "Personal".
2. UPDATE auf alle Persona/Playbook/Token-Rows: `workspace_id = <neuer Personal-Workspace>`.
3. `workspace_member`-Row anlegen mit Rolle `admin` fuer den User — schon heute, damit 2.3 kein Backfill mehr braucht.

Test in `apps/api/tests/test_migrations.py`: Migration-Idempotenz + Cardinality-Check (jeder pre-existing owner_id hat genau eine Personal-Org).

### 2.1.C — API-Schwenk

Path-Praefix `/v1/workspaces/{workspace_id}/...` fuer alle existierenden Endpoints. Aenderungen in:

- `apps/api/src/who2be_api/main.py` — `include_router(personas.router, prefix="/v1/workspaces/{workspace_id}")`.
- Neue Dependency `apps/api/src/who2be_api/core/security.py::get_current_workspace(workspace_id, user)`:
  - Resolved `workspace_id` aus Path **oder** aus dem Token (wenn API-Token mit gepinntem `workspace_id`).
  - Bei Mismatch → 403.
  - Prueft Workspace-Mitgliedschaft via `workspace_member` (in 2.1 immer truthy fuer Owner, in 2.3 echt gefiltert).
  - Returnt `WorkspaceContext(workspace_id, user_id, role)` als Annotated-Dep.
- Alle Service-Methoden (`apps/api/src/who2be_api/services/{persona,playbook,token,persona_playbook}_service.py`): `owner_id: UUID` → `ctx: WorkspaceContext`. Repos analog (`apps/api/src/who2be_api/repositories/*.py`): `WHERE owner_id = $1` → `WHERE workspace_id = $1` in allen `_SELECT_CURRENT`-Queries (siehe `apps/api/src/who2be_api/repositories/persona_repository.py:18-25` als Vorlage).
- **Neue Router** unter `apps/api/src/who2be_api/routers/`:
  - `organizations.py` — `GET/POST/PATCH/DELETE /v1/organizations` (User-eigene Orgs), `GET /v1/organizations/{id}/workspaces`.
  - `workspaces.py` — `POST /v1/organizations/{org_id}/workspaces`, `GET/PATCH/DELETE /v1/workspaces/{id}`.
  - `dashboard.py` — `GET /v1/workspaces/{ws_id}/dashboard` (siehe 2.1.E).
- **Status-Endpoints** pro Entity-Typ:
  - `POST /v1/workspaces/{ws_id}/personas/{id}/versions/{v}/transition` Body `{to: 'review'|'active'|...}`. Service validiert erlaubten Uebergang + DB-Constraint setzt Invariante durch. Schreibt `status_history`.
  - **Edit-Verhalten:** PUT auf eine Active-Persona erzeugt eine **neue** Draft-Version (`current_version + 1`, status='draft'). Active-Version bleibt unangetastet. Wenn schon ein Draft existiert: 409 mit Hinweis "Promote oder verwirf bestehenden Draft erst".

### 2.1.D — MCP-Anpassungen (`apps/mcp/src/who2be_mcp/`)

- Token-pro-Workspace heisst: kein neuer Tool-Parameter, der Server kennt den Workspace aus dem Token.
- In `client.py`: HTTP-Adapter ergaenzt `workspace_id` automatisch im Pfad (`/v1/workspaces/{ws_id}/...`) — Resolution einmal bei Server-Start via `GET /v1/me/token-context`.
- `get_persona` / `list_playbooks` / `fetch_playbook` filtern auf `status='active'` (Server-seitig in den Services, MCP muss nichts wissen).
- Keine neuen MCP-Tools in 2.1 — Resources kommen erst in 2.2.

### 2.1.E — Dashboard-Endpoint

`GET /v1/workspaces/{ws_id}/dashboard` returnt:

```json
{
  "kpis": {
    "active_personas": 12,
    "active_playbooks": 34,
    "pending_reviews": 3
  },
  "activity": [
    {"ts": "...", "actor": {...}, "entity_type": "playbook", "entity_id": "...", "event": "promoted_to_active", "from_version": 3, "to_version": 4}
  ],
  "status_distribution": {
    "persona": {"draft": 2, "review": 1, "active": 12, "inactive": 8},
    "playbook": {...}
  }
}
```

Datenquelle: `status_history` (Activity) + Aggregat-Query ueber `*_version` (Distribution). Cached pro Request (in-memory LRU mit 30s TTL, optional).

### 2.1.F — Web-UI

- `apps/web/src/auth/` — neuer `WorkspaceContext` + `useCurrentWorkspace()`-Hook.
- **Router-Umbau** `apps/web/src/main.tsx`:
  - `/login` (wie heute)
  - `/orgs/new` (Setup falls noch keine Org)
  - `/w/:workspaceId/dashboard`
  - `/w/:workspaceId/personas` / `.../personas/new` / `.../personas/:id`
  - `/w/:workspaceId/playbooks` / ...
  - `/w/:workspaceId/settings/tokens`
  - `/w/:workspaceId/settings/workspace` (Name, Slug, spaeter Member)
  - `/settings/orgs` (Org-uebergreifend: Liste eigener Orgs, Create-Org)
- **AppShell** (`apps/web/src/app/AppLayout.tsx`):
  - Workspace-Switcher links oben: zweistufiger Dropdown (Org → Workspace).
  - Beim Wechsel: Route auf `/w/{neue_ws_id}/dashboard`. Persistiert letzte Auswahl in `localStorage` als Default beim naechsten Login.
  - Wenn User keine Workspaces hat → Redirect `/orgs/new`.
- **API-Client** (`apps/web/src/api/client.ts`): bekommt `workspaceId` als Required-Constructor-Argument; Methoden bauen URLs `/v1/workspaces/{ws_id}/...`.
- **Status-UI** in `PersonaDetailPage`/`PlaybookDetailPage`:
  - Header zeigt: "Aktive Version: v3 · Du bearbeitest: v4 (Draft)".
  - Action-Bar mit Buttons: **Submit for Review**, **Promote to Active**, **Reject** (kontextabhaengig von State + Rolle).
  - Versions-Liste rechts mit Status-Badge je Zeile.
- **Dashboard-Page** `apps/web/src/features/dashboard/pages/DashboardPage.tsx`:
  - 3 KPI-`Card`s aus `@/components/ui/card`.
  - Activity-Feed: `DataList` aus `@/components/data/DataList`.
  - Status-Verteilung: einfache horizontale Stacked-Bar — entweder als CSS-Grid (kein Charting-Lib) oder via Recharts (neue Dep). **Default ohne neue Dep**: CSS-Grid mit semantischen Farben aus `globals.css`.
- ESLint-Gates aus `apps/web/eslint.config.js` bleiben aktiv (nur shadcn-Primitives, kein direktes `<button>`, kein Cross-Feature-Deep-Import).

### 2.1.G — Models (`packages/models/src/who2be_models/`)

- Neue Files: `organization.py`, `workspace.py`, `status.py` (Enum), `dashboard.py`, `status_history.py`.
- Bestehende `PersonaRead`/`PlaybookRead`: Felder `workspace_id`, `current_status` (= Status der `current_version`), `has_pending_draft: bool`.
- Versions-Modelle (`PersonaVersionRead`/`PlaybookVersionRead`): `status`-Feld.
- Pydantic-`max_length` bleibt durchgaengig (F-01-Linie nicht durchbrechen).

### 2.1.H — Tests

Pro Touched-File:
- Repository-Test mit echter Postgres-Migration (pytest-Marker `integration`, siehe `apps/api/tests/test_personas.py` als Vorlage).
- Status-Transition-Tests: erlaubte Uebergaenge gruen, verbotene 409, DB-Invariante "max. 1 Active" via duplizierter Insert sichtbar.
- Backfill-Migration-Test: existierende Daten landen im richtigen Workspace.
- Web-Smoke fuer Switcher (`apps/web/src/app/AppLayout.test.tsx`).
- A11y-Gate fuer Dashboard-Page (vitest-axe).

### 2.1.I — Deliverable

PR splittet in zwei Stuecke:
1. **`feat/2.1a-tenancy`** — Datenmodell + Migration + API-Schwenk + MCP-Anpassung + bestehende Web-Pages auf neuen Pfad. Existierende Features funktionieren wie vorher, nur unter `/w/{ws_id}/...`.
2. **`feat/2.1b-status-dashboard`** — Status-pro-Version + Status-UI + Dashboard-Endpoint + Dashboard-Page.

Neuer ADR `docs/adr/0019-tenant-org-workspace.md` (Modell + Trade-offs Personal-Org-Auto-Create) und `0020-status-pro-version.md`.

---

## Phase 2.2 — Resources mit Block-Editor

**Ziel:** Resources als zweite Wissensebene; Playbooks koennen auf einzelne oder mehrere Bloecke einer Resource verweisen.

### 2.2.A — Datenmodell

- `0014_resource.sql`
  - `resource(id, workspace_id, name, current_version, created_at, updated_at, created_by)`
  - `resource_version(resource_id, version, content jsonb, status enum, created_at, created_by)` — analog Persona/Playbook (ADR-0004-Muster). Partial Unique Index fuer `status='active'` analog 2.1.
- `0015_playbook_resource_link.sql`
  - `playbook_resource_link(workspace_id, playbook_id, resource_id, block_id text, position smallint, created_at)`
  - Composite-FK `(workspace_id, playbook_id)` und `(workspace_id, resource_id)` — Defense-in-Depth wie heute.
  - `block_id` ist ein TipTap-Node-`id`-Attribut (UUID-String).
  - Eindeutigkeit `(playbook_id, resource_id, block_id)` per Unique-Index.

### 2.2.B — Resource-Content-Format

`resource_version.content` ist TipTap-JSON (ProseMirror-Doc):

```json
{
  "type": "doc",
  "content": [
    {"type": "heading", "attrs": {"level": 1, "id": "<uuid>"}, "content": [{"type": "text", "text": "..."}]},
    {"type": "paragraph", "attrs": {"id": "<uuid>"}, "content": [...]},
    ...
  ]
}
```

**Stable-Block-ID-Extension** ist Pflicht: TipTap-Extension `BlockId` haengt jedem Top-Level-Node ein `id`-Attribut an (UUID, generiert beim Insert, persistiert in JSON). Vorlage: TipTap UniqueID-Extension oder Eigenbau (~30 LoC).

**Block-Types fuer MVP** (Schluss-Liste): `paragraph`, `heading` (Level 1-3), `bulletList`/`orderedList`, `codeBlock`, `blockquote`, `horizontalRule`. **Nicht im MVP:** Image, Table, Embed, Callout, Toggle — explizit ausgeklammert, sonst sprengt 2.2.

### 2.2.C — API-Endpoints

Neuer Router `apps/api/src/who2be_api/routers/resources.py`:

- `GET /v1/workspaces/{ws}/resources?limit&cursor` — Keyset-Pagination wie Personas.
- `POST /v1/workspaces/{ws}/resources` — anlegen mit initialem Draft.
- `GET /v1/workspaces/{ws}/resources/{id}` — Active-Version (falls vorhanden) + Liste aller Versionen.
- `GET /v1/workspaces/{ws}/resources/{id}/versions/{v}` — konkrete Version.
- `PUT /v1/workspaces/{ws}/resources/{id}` — Edit (erzeugt Draft, wie 2.1).
- `DELETE /v1/workspaces/{ws}/resources/{id}`.
- `POST /v1/workspaces/{ws}/resources/{id}/versions/{v}/transition` — Status-Wechsel.
- `GET /v1/workspaces/{ws}/playbooks/{id}/resource_links` — alle Links + `available`-Flag (Block existiert im aktuellen Resource-Active-Stand?).
- `PUT /v1/workspaces/{ws}/playbooks/{id}/resource_links` — Set-Replace mit Body `{links: [{resource_id, block_id, position}]}`.

Service-Layer: `apps/api/src/who2be_api/services/resource_service.py`, `playbook_resource_link_service.py`.
Repository: `apps/api/src/who2be_api/repositories/resource_repository.py` (Pattern aus `persona_repository.py`).

### 2.2.D — MCP-Erweiterung

`apps/mcp/src/who2be_mcp/server.py` neue Tools:

- `list_resources(tag?)` — Active-Resources mit `id`, `name`, `block_count`.
- `fetch_resource(resource_id, block_ids?)` — gibt entweder die ganze Active-Version oder nur die angeforderten Bloecke zurueck.
- Bestehendes `fetch_playbook` erweitert um `linked_blocks: [{resource_id, block_id, available: bool, preview: text?}]` — Preview ist erste 200 Zeichen des Block-Plain-Text, ohne Auto-Inline.

Neuer ADR `0021-mcp-resource-tools.md`.

### 2.2.E — Web-Editor

- Neue Dep: `@tiptap/react`, `@tiptap/starter-kit`, `@tiptap/extension-placeholder`. Slash-Menu/Drag-Handle selbst — kein `@blocknote/*`.
- Neuer Ordner `apps/web/src/features/resources/` (Pages, Components, Editor-Komponenten):
  - `pages/ResourcesPage.tsx`, `ResourceNewPage.tsx`, `ResourceDetailPage.tsx`.
  - `components/Editor/` mit `ResourceEditor.tsx` (TipTap-Wrapper), `BlockShell.tsx` (Drag-Handle + Add-Button, Floating-UI), `SlashMenu.tsx` (Radix-Popover mit gefilterter Liste der MVP-Block-Types), `BlockIdExtension.ts`.
  - Toolbar mit shadcn-`Button`-Group; Inline-Marks (Bold/Italic) via TipTap-Default.
- **Playbook-Editor erweitert** (`apps/web/src/features/playbooks/components/`): neue `BlockLinkPicker.tsx` — modaler `Dialog` mit zweispaltigem Layout (links Resource-Liste, rechts Block-Vorschau der gewaehlten Resource, Mehrfach-Auswahl mit Checkbox je Block).
- **Linked-Blocks-Display** auf Playbook-Detail-Page: Liste mit Block-Vorschau + Status-Badge ("Block geloescht" wenn `available=false`, mit Action "Link entfernen").
- ESLint-Gates beachten — alle Inputs/Buttons aus `@/components/ui/*`.

### 2.2.F — Tests

- Editor-Smoke (vitest + jsdom + @testing-library): Block einfuegen, Slash-Menu oeffnen, Block-Type wechseln.
- BlockId-Persistenz: Serialize → Deserialize behaelt IDs.
- API: Resource-Versionierung (analog Persona-Tests), Link-Set-Replace atomar.
- MCP: `fetch_resource` mit / ohne `block_ids`-Filter, `available=false` wenn Block fehlt.
- A11y-Gate fuer Editor-Page (axe gegen die Toolbar, nicht den Editor-Content selbst — TipTap-Content braucht manuelle a11y-Checks).

### 2.2.G — Deliverable

Ein PR `feat/2.2-resources`. Migration-Files, ADR `0021-mcp-resource-tools.md`, ADR `0022-tiptap-editor-stack.md` (Stack-Wahl + warum nicht BlockNote).

---

## Phase 2.3 — Multi-User pro Workspace

**Ziel:** Org-Owner und Workspace-Admins koennen andere User in Workspaces einladen mit Rollen `admin`/`editor`/`viewer`. RBAC wird im Backend durchgesetzt; Status-Workflow bekommt echten Reviewer.

### 2.3.A — Datenmodell

`workspace_member`-Tabelle existiert seit 2.1 — wird in 2.3 erstmals echt benutzt. Zusaetzlich:

- `0016_invitations.sql`
  - `workspace_invitation(id, workspace_id, email, role, token_hash, expires_at, created_by, accepted_at?, revoked_at?)` — Token nur als Hash, Klartext geht per Mail raus.

### 2.3.B — Autorisierung

- `get_current_workspace` Dependency (existiert seit 2.1) wird jetzt scharf gestellt:
  - Prueft `workspace_member`-Row.
  - Returnt Rolle; alle Mutations-Endpoints pruefen `role in {admin, editor}` (Viewer = read-only).
- `transition`-Endpoint pro Entity-Typ: Promotion auf `active` nur fuer Rolle `admin` (= "Reviewer"). Editor darf Draft → Review pushen, nicht Review → Active.
- API-Token: Token kann nicht hoehere Rechte haben als der Ersteller. Token speichert `created_by_user_id` + `role` (snapshot). Bei Token-Use wird die Snapshot-Rolle benutzt, nicht die aktuelle Rolle (Verhindert Privilege-Drift).

### 2.3.C — API + Web

- Neue Router-Pfade unter `workspaces.py`:
  - `GET /v1/workspaces/{ws}/members`
  - `POST /v1/workspaces/{ws}/invitations` (Body: email, role)
  - `DELETE /v1/workspaces/{ws}/invitations/{id}`
  - `POST /v1/invitations/{token}/accept` (anonym mit Mail-Token; setzt `workspace_member`)
  - `PATCH /v1/workspaces/{ws}/members/{user_id}` (Rollen-Aenderung)
  - `DELETE /v1/workspaces/{ws}/members/{user_id}`
- Mail via Supabase GoTrue (`POST /auth/v1/invite` als Wrapper) ODER eigener SMTP-Hook. **Default: GoTrue**, weil schon im Stack.
- Web: `/w/{ws}/settings/members` mit Member-Tabelle + Invite-Form. Status-Action-Bar respektiert Rolle (Promote-Button disabled fuer Editor).

### 2.3.D — Tests

- RBAC-Matrix-Test: jede Rolle × jeder Mutating-Endpoint → erwartetes 200/403.
- Invitation-Flow E2E (httpx-ASGI): invite → accept (anderer User) → Member sichtbar.
- Snapshot-Rolle bei Token: User von Admin auf Editor downgraden → Token verhaelt sich weiter wie Admin (gewuenscht? — wird in ADR `0023-multi-user-rbac.md` festgehalten).

### 2.3.E — Deliverable

Ein PR `feat/2.3-multi-user` + ADR `0023-multi-user-rbac.md`. CLAUDE.md-Update mit neuem aktuellen Stand.

---

## Cross-cutting

- **Security**: Subagent `security-reviewer` ueber jede Phase laufen lassen. Achten auf: Cross-Workspace-Read (Composite-FK + `WHERE workspace_id = $1` in **jedem** Query), Invite-Token-Replay (single-use), Status-Promotion ohne Member-Check, TipTap-XSS (Renderer muss Output sanitisieren — kein `dangerouslySetInnerHTML` ohne DOMPurify).
- **Caddy/CSP**: Resource-Editor laedt evtl. Web-Fonts oder CDN-Assets — CSP-Whitelist in `deploy/hetzner/Caddyfile` anpassen.
- **Logging**: `structlog`-Context erweitert um `workspace_id` (vergleichbar `owner_id` heute in `apps/api/src/who2be_api/core/security.py:94`).
- **Pagination**: Bestehende `apps/api/src/who2be_api/core/pagination.py` Keyset-Codec wiederverwenden fuer Resources + Members.
- **CI**: `.github/workflows/ci.yml` muss nichts neues — Migrations laufen automatisch im Postgres-Service.

## Verifikation

**Pro Phase, vor Merge:**

- Python: `uv run ruff check .` clean · `uv run mypy .` clean · `uv run pytest -q` gruen (inkl. neuer Integrations-Tests gegen lokales Postgres).
- Web: `npm run lint` clean · `npx tsc --noEmit` clean · `npm test` gruen · `npm run build` ohne Warnings.
- Smoke: `docker compose up -d`, manueller Run-Through der neuen Pages laut `docs/local-smoke.md` (Datei pro Phase ergaenzen).

**Phase 2.1 End-to-End:**
- Login → AppShell zeigt "Personal · Personal-Workspace" als Default.
- Org anlegen via `/settings/orgs` → erscheint im Switcher.
- Workspace in der Org anlegen → erscheint im Switcher.
- Persona im neuen Workspace ist im alten nicht sichtbar.
- Persona editieren erzeugt Draft; Promote to Active aktualisiert MCP-Output (`uv run python -m who2be_mcp.server` + Client-Call gegen lokalen API).
- Dashboard zeigt Activity-Eintraege + Status-Bar.

**Phase 2.2 End-to-End:**
- Resource anlegen, mehrere Bloecke einfuegen via Slash-Menu, Promote to Active.
- Im Playbook BlockLinkPicker oeffnen, Bloecke auswaehlen, speichern.
- `fetch_playbook` ueber MCP zeigt `linked_blocks` mit Pointern; `fetch_resource(ws_id, [block_ids])` liefert die Bloecke.
- Resource-Block loeschen + neue Version Active → Playbook-Detail zeigt "Block geloescht"-Badge.

**Phase 2.3 End-to-End:**
- Admin lade per Mail einen zweiten User ein → User akzeptiert → erscheint in Member-Liste.
- Zweiter User loggt sich ein, sieht Workspace im Switcher, kann als Editor Drafts erstellen, aber **kein** Promote auf Active.
- Admin promotet Editor-Draft.

## Kritische Dateien (Touch-Points)

- Auth/Tenant-Dep: `apps/api/src/who2be_api/core/security.py` (neue `get_current_workspace`).
- App-Bootstrap: `apps/api/src/who2be_api/main.py` (Router-Prefix-Umbau).
- Repositories-Pattern (alle gleich umzubauen): `apps/api/src/who2be_api/repositories/*.py` — Vorlage `persona_repository.py`.
- Services-Pattern: `apps/api/src/who2be_api/services/*.py` — `owner_id` → `WorkspaceContext`.
- Migrations: `apps/api/src/who2be_api/migrations/` (0005-0016, sequenziell).
- MCP-Client: `apps/mcp/src/who2be_mcp/client.py` (URL-Prefix), `server.py` (neue Tools in 2.2).
- Web-Router: `apps/web/src/main.tsx` (URL-Schema), `apps/web/src/app/AppLayout.tsx` (Switcher).
- Web-API-Client: `apps/web/src/api/client.ts` (Workspace-Bindung).
- ESLint-Gates bleiben unveraendert: `apps/web/eslint.config.js`.
- Designsprache-Vertrag: `docs/frontend/design-language.md` — vor jeder UI-Aenderung lesen.

## ADR-Backlog

- `0019-tenant-org-workspace.md` — Hierarchie + Personal-Org-Auto-Create
- `0020-status-pro-version.md` — State-Machine + DB-Invariante
- `0021-mcp-resource-tools.md` — neue MCP-Tools + kein Auto-Inline
- `0022-tiptap-editor-stack.md` — TipTap-Wahl gegen BlockNote
- `0023-multi-user-rbac.md` — Rollen + Token-Rollen-Snapshot
