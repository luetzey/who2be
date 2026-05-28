# ADR-0019 — Tenant-Hierarchie: User → Organization → Workspace

- Status: Akzeptiert
- Datum: 2026-05-28
- Kontext: Who2Be Phase 2.1 — Vollwertige Multi-Tenant-App

## Kontext

Der MVP isoliert alle Daten ueber `owner_id` (Supabase-User-UUID) auf
`persona`, `playbook` und `api_token`. Damit ist Who2Be ein
Single-User-System: pro User eine private Datenmenge, kein Konzept fuer
Teams, kein Konzept fuer mehrere Mandanten je User. Fuer eine vollwertige
App brauchen wir:

- **Trennung "wer bezahlt" von "wo arbeitet"** — eine Organization mit
  mehreren Workspaces (z.B. "Marketing", "Engineering").
- **Mehrere User pro Tenant** (in Phase 2.3 echt benutzt, hier nur
  vorbereitet) — eine Membership-Tabelle, die heute schon befuellt wird.
- **Migration ohne Datenverlust** fuer Bestandsdaten der MVP-User.

Plan-Vorlage: `.claude/plan/2026-05-27-1921_phase-2-vollwertige-app.md`,
§2.1 (faktisch umgesetzt in Phase 2.1a, PR #38).

## Optionen

- **A — Flach: `User → Workspace`.** Workspaces direkt am User. Kein
  Org-Konstrukt. Spart eine Tabelle und einen Indirection-Schritt.
  Bricht aber das Modell "Organization als Abrechnungs- und
  Mitgliedschafts-Einheit" und erzwingt spaeter eine teure Migration,
  wenn ein User in zwei Firmen Mitglied sein soll.
- **B — `User → org_member → Organization → Workspace → Entity`
  (gewaehlt).** Volle Hierarchie mit getrennten Mitgliedschafts-Tabellen
  pro Ebene (`org_member`, `workspace_member`). Personal-Orgs (`kind =
  'personal'`) decken den Single-User-Fall ab — UI rendert sie als
  "Personal", DB behandelt sie gleich.
- **C — Single-Tenant-Forever.** Status quo (`owner_id` ueberall). Kein
  Migrationsschmerz; macht Teams und Multi-Workspace aber unmoeglich.

## Entscheidung

**Option B.**

Schema (umgesetzt in Migrations 0005-0010 + 0013, siehe
`apps/api/src/who2be_api/migrations/`):

- `organization(id, name, slug, kind, created_at)` mit
  `kind IN ('personal','company')`, Unique `(kind, slug)`.
- `org_member(org_id, user_id, role, invited_by, joined_at)`
  mit `role IN ('owner','admin','member')`, Composite-PK `(org_id, user_id)`.
- `workspace(id, org_id, name, slug, created_at)`,
  Unique `(org_id, slug)`.
- `workspace_member(workspace_id, user_id, role, joined_at)`
  mit `role IN ('admin','editor','viewer')`, Composite-PK.
- `persona`, `playbook`, `api_token` bekommen `workspace_id` (`NOT NULL`
  nach Backfill, FK, Index).
- `persona_playbook`-Composite-FKs schwenken auf
  `(workspace_id, persona_id) → persona(workspace_id, id)` und analog
  Playbook (Defense-in-Depth wie heute der `(owner_id, …)`-Switch in
  `0004_persona_playbook.sql`).

**Personal-Org-Auto-Create + Backfill** (`0013_backfill_tenants.sql`):

- Pro distinct `owner_id` aus `persona ∪ playbook ∪ api_token`: eine
  Personal-`organization` (`kind = 'personal'`), ein Default-Workspace
  "Personal", ein `org_member` (`role = 'owner'`), ein
  `workspace_member` (`role = 'admin'`).
- `UPDATE` auf bestehende Rows: `workspace_id = <neuer Personal-WS>`.

**Owner-Spalte bleibt als Audit-Feld.** `owner_id` auf `persona`,
`playbook`, `api_token`, `persona_playbook` wird **nicht** gedroppt —
dokumentiert in §2.1.A des Plans als "bitter zu droppen, billig zu
behalten". Liefert `created_by` in Logs und `changed_by` in
`status_history`-Eintraegen.

**API-Routing.** Alle existierenden Endpoints leben unter
`/v1/workspaces/{workspace_id}/...`. Eine Dependency
`get_current_workspace` (`apps/api/src/who2be_api/core/security.py`)
resolved `workspace_id` aus dem Pfad oder dem API-Token (Workspace-pinned),
prueft Mitgliedschaft via `workspace_member` und gibt einen
`WorkspaceContext` an die Services. Bei Mismatch: 403.

**Token-Scope pro Workspace.** API-Token tragen `workspace_id` — ein
Token aus Workspace A kann Workspace B nicht ansprechen.

**Web-URL-Schema.** `/w/{ws_id}/...`. Letzte Auswahl im
`localStorage` als Default beim naechsten Login. Workspace-Switcher in
der AppShell.

## Konsequenzen

- Repository-Layer filtert konsequent auf `workspace_id`
  (`_SELECT_CURRENT` in allen Repos), nicht mehr auf `owner_id`. Damit
  Cross-Workspace-Leaks ausgeschlossen sind, wird `WHERE workspace_id =
  $1` in jedem Query Pflicht — `security-reviewer` prueft das pro PR.
- `workspace_member` ist ab 2.1 befuellt, wird aber erst in 2.3 fuer
  echte RBAC ausgewertet. Damit muss Phase 2.3 **keinen** weiteren
  Backfill fahren.
- Phase 2.3 fuegt Invitations (`workspace_invitation`) hinzu — Tabelle
  existiert heute nicht, kommt in ADR-0023.
- Roll-Back ist teuer: Daten-Backfill ist einseitig (Personal-Orgs sind
  jetzt der Single-Source-of-Truth). Wenn die Hierarchie sich als falsch
  herausstellt, gibt es kein einfaches Down-Migration — wir muessten
  Personal-Org-Slugs zurueck auf `owner_id` mappen. Akzeptiert als
  Einbahnstrasse.
- Mailing-Pfad fuer Invitations und Rollen-UI (Member-Liste,
  Invite-Form, Promote-/Demote-Aktionen) sind explizit aus dem Scope
  von ADR-0019 — folgen in ADR-0023.
