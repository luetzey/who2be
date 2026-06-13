# Who2Be — Vollständiger Funktionstestplan (User & Agenten)

> **Stand:** 2026-06-09 · **Geltungsbereich:** Alle aktuell im Code vorhandenen, vom User
> ausführbaren Funktionen — über die Web-UI **und** über Agenten (MCP).
> **Quelle:** Code-Inventur von `apps/api` (REST), `apps/mcp` (FastMCP) und `apps/web` (React).
> **Zweck:** Ein kompletter manueller Durchlauf, mit dem du als User verifizierst, dass jede
> Funktion end-to-end funktioniert. Hake jeden Fall ab.

## Wie dieser Plan zu lesen ist

- **Test-ID:** `FT-<STRANG>-<NR>` — eindeutig referenzierbar.
- **Oberfläche:** `UI` (Web), `API` (REST direkt, z.B. via curl/HTTPie), `MCP` (Agent/Tool).
  Viele Funktionen sind über mehrere Oberflächen testbar — dann ist die primäre genannt.
- **Rolle:** Minimal nötige Workspace-Rolle (`viewer` < `editor` < `admin`) bzw. `owner` (Org).
- **Erwartung:** Sichtbares Soll-Ergebnis inkl. relevanter Statuscodes.
- ✅-Spalte zum Abhaken in deiner Kopie.

## Status-Legende (Versionierungs-State-Machine)

Gilt für **Persona, Playbook, Resource, System-Prompt-Template**:

```
draft ──(Submit, editor)──▶ review ──(Publish, admin)──▶ active ──(Retire, admin)──▶ inactive
  ▲                            │                            │                          │
  └──(Reject, editor)──────────┘                            │                          │
  ◀──(Reset, admin)─────────────────────────────────────────┘                          │
  ◀──(Reaktivieren als Draft, editor)──────────────────────────────────────────────────┘
```

- **Agenten (MCP-Reads) sehen ausschließlich `status='active'`.** Drafts/Review/Inactive sind unsichtbar.
- PUT auf eine aktive Version erzeugt einen neuen **Draft** (→ **409**, wenn bereits ein Draft existiert).
- Jeder Übergang **ab `active`** erfordert **admin** — Promote (→active), Retire (active→inactive) **und Reset (active→draft)** (ADR-0023, durchgesetzt in `version_status.py::required_role_for_transition`). Übrige Transitionen (Submit, Reject, Reaktivieren) erfordern **editor**.

---

# 0 · Testvorbereitung

| ID | Ziel | Oberfläche | Rolle | Schritte / Erwartung | ✅ |
|----|------|-----------|-------|----------------------|----|
| FT-PREP-01 | Stacks starten | — | — | `docker compose up -d`; API: `uv run uvicorn who2be_api.main:app --reload`; MCP: `uv run python -m who2be_mcp.server`; Web: `npm run dev`. Alle drei laufen ohne Fehler. **Für einen vollwertigen Lauf zwingend DB/GoTrue/Mailcatcher (Setup: `docs/local-smoke.md`).** Tipp: `WHO2BE_REQUIRE_DB=1` setzen, damit DB-abhängige Pfade hart **fehlschlagen** statt zu skippen — verhindert „grün durch Skip" bei den 31 BLOCKED-IDs. | |
| FT-PREP-02 | Health-Check | API | anon | `GET /v1/health` → **200**, Body mit `status`, `version`, DB-Konnektivität. | |
| FT-PREP-03 | MCP-Liveness | MCP | anon | Tool `ping` → `"pong"`. | |
| FT-PREP-04 | Testkonten anlegen | UI | — | Mind. **3 User**: einer wird `admin`, einer `editor`, einer `viewer` (im selben Workspace). Für Tenancy-Tests ein 4. User ohne Mitgliedschaft. | |
| FT-PREP-05 | Rollen-Matrix-Vorsatz | — | — | Jeden mutierenden Testfall **zusätzlich** als `viewer` durchspielen → muss **403** / deaktivierte UI ergeben (siehe Strang T). | |

---

# A · Auth & Onboarding (UI)

| ID | Ziel | Rolle | Schritte / Erwartung | ✅ |
|----|------|-------|----------------------|----|
| FT-AUTH-01 | Signup mit Consent | — | `/signup`: Email + Passwort (≥8) + Passwort-Bestätigung; **Consent-Checkbox** (AGB & Datenschutz) ist Pflicht. Submit- und OAuth-Buttons bleiben gesperrt, bis Consent gesetzt. → „Confirmation pending"-State. | |
| FT-AUTH-02 | Email-Bestätigung | — | Bestätigungs-Mail-Link → `/auth/callback` → Session etabliert → Redirect auf `?next` bzw. Dashboard. 4s-Timeout-Fallback testen (Link ohne gültigen Hash). | |
| FT-AUTH-03 | Login | — | `/login`: korrekte Credentials → Redirect. Falsche → Fehler. Unbestätigte Email → „Resend Confirmation"-Button erscheint. | |
| FT-AUTH-04 | OAuth-Login | — | Google/GitHub-Button (sofern konfiguriert) → Callback → Session. | |
| FT-AUTH-05 | Passwort-Reset | — | `/reset-password`: Email eingeben → „Mail gesendet"-State → Reset-Link → neues Passwort. | |
| FT-AUTH-06 | `next`-Redirect-Härtung | — | Login mit `?next=https://evil.example` → **kein** Open-Redirect; nur interne Pfade werden gefolgt. | |
| FT-AUTH-07 | Set-Password (Onboarding) | — | Nach Magic-Link/OAuth ohne Passwort → `/onboarding/set-password` (≥8) → Redirect auf `?next`. | |
| FT-AUTH-08 | Legal-Seiten öffentlich | anon | `/legal/impressum`, `/legal/terms`, `/legal/privacy`, `/legal/dpa` ohne Auth erreichbar. | |

---

# B · Organisation, Workspace & Tenancy

| ID | Ziel | Oberfläche | Rolle | Schritte / Erwartung | ✅ |
|----|------|-----------|-------|----------------------|----|
| FT-ORG-01 | Orgs auflisten | API/UI | auth | `GET /v1/organizations` → eigene Orgs. | |
| FT-ORG-02 | Org anlegen | API | auth | `POST /v1/organizations` → **201**. | |
| FT-ORG-03 | Workspace anlegen | UI | auth | Org-Settings → „Neuer Workspace" bzw. `POST /v1/organizations/{id}/workspaces` → **201**. | |
| FT-ORG-04 | Workspaces der Org | API/UI | member | `GET /v1/organizations/{id}/workspaces`. | |
| FT-ORG-05 | Workspace umbenennen | UI | admin | Workspace-Settings → Rename-Dialog → Name aktualisiert (`PATCH /v1/workspaces/{id}`). | |
| FT-ORG-06 | Letzter Workspace geschützt | UI | admin | Versuch, den **einzigen** Workspace der Org zu löschen → **409** (Schutz greift). | |
| FT-ORG-07 | Workspace löschen | UI | admin | Bei ≥2 Workspaces: Danger-Zone → Bestätigung → **204**. | |
| FT-ORG-08 | Org löschen (nur leer) | API | owner | `DELETE /v1/organizations/{id}` nur durch Owner; Soft-Delete mit 30-Tage-Frist → **204**. | |
| FT-ORG-09 | WorkspaceSwitcher | UI | member | Switcher im Sidebar: zweistufig (Orgs → Workspaces), Häkchen am aktiven, „Workspace erstellen". Auswahl navigiert auf `/w/{id}/dashboard`, merkt sich Auswahl (localStorage). | |
| FT-ORG-10 | Tenancy-Isolation | API | — | User **ohne** Mitgliedschaft ruft `/v1/workspaces/{fremde_id}/...` → **403/404**. Keine fremden Daten sichtbar. | |
| FT-ORG-11 | `/v1/me` | API | auth | Identität + Memberships + Default-Workspace korrekt. | |

---

# C · Mitglieder, Rollen & Einladungen (RBAC)

| ID | Ziel | Oberfläche | Rolle | Schritte / Erwartung | ✅ |
|----|------|-----------|-------|----------------------|----|
| FT-RBAC-01 | Mitglieder auflisten | UI | member | Members-Page → Tabelle (Email, Rolle, Aktionen). | |
| FT-RBAC-02 | Members-Page admin-only | UI | editor/viewer | Aufruf als editor/viewer → Redirect auf Dashboard + Fehler-Toast. | |
| FT-RBAC-03 | Einladung erstellen | UI | admin | Invite-Form: Email + Rolle (admin/editor/viewer) → **201**; Accept-Link erscheint mit Copy-Button (Token **einmalig** sichtbar). | |
| FT-RBAC-04 | Offene Einladungen | UI | admin | Pending-Tabelle zeigt Email/Rolle/Link/Revoke. | |
| FT-RBAC-05 | Einladung widerrufen | UI | admin | Revoke → **204**; Token danach ungültig. | |
| FT-RBAC-06 | Einladung annehmen (manuell) | UI | — | `/invitations/{token}/accept` mit Session → „Accept" → Redirect auf Workspace-Dashboard; Mitglied mit korrekter Rolle. | |
| FT-RBAC-07 | Magic-Link-Annahme | UI | — | Accept-URL mit `?via=magic`: ohne Session → `/login?next=…`; ohne Passwort → `/onboarding/set-password?next=…`; dann Auto-Accept. | |
| FT-RBAC-08 | Email-Mismatch-Guard | UI | — | Eingeloggter User ≠ eingeladene Email → klare Fehlermeldung, **keine** Annahme. | |
| FT-RBAC-09 | Abgelaufen/benutzt | API | — | `POST /v1/invitations/{token}/accept` auf benutzten/widerrufenen/abgelaufenen Token → **410 Gone**. | |
| FT-RBAC-10 | Rolle ändern | UI | admin | Mitgliedsrolle ändern (`PATCH …/members/{user}`) → wirkt sofort. Downgrade zeigt Token-Downgrade-Warnung. | |
| FT-RBAC-11 | Mitglied entfernen | UI | admin | Remove → **204**; Zugriff entzogen. | |
| FT-RBAC-12 | Rollen-Durchsetzung | API | viewer/editor | Mutierende Endpoints als viewer → **403**; Promote/Retire als editor → **403** (nur admin). | |

---

# D · Personas

| ID | Ziel | Oberfläche | Rolle | Schritte / Erwartung | ✅ |
|----|------|-----------|-------|----------------------|----|
| FT-PER-01 | Liste + Pagination | UI/API | member | `/personas`: DataList, Versions-Badge; `X-Next-Cursor`-Header bei `limit`. Empty-State bei 0. | |
| FT-PER-02 | Persona anlegen | UI | editor | `/personas/new`: Sprache wählen, Editor ausfüllen, „Erstellen" → **201**, neue Version 1 als **draft**. | |
| FT-PER-03 | Detail/Edit | UI | editor | Name, Trigger, Tags (TagInput), Profil-Body (BlockNote-Insel). Änderungen werden auto-gespeichert (Indikator „Saving…/Saved Xs ago"). | |
| FT-PER-04 | Auto-Save-Draft | API | editor | `PATCH …/personas/{id}/draft` upsert ohne Versions-Inkrement → **200**. | |
| FT-PER-05 | Persona-Modi | UI | editor | PersonaModesDisclosure: Mode hinzufügen (Name, Trigger, Default-Radio exklusiv, Playbook-Select, 3 BlockNote-Inseln: Identity-Add/Output-Style/Anti-Patterns). InfoPill zeigt „N Modes • Default: …". | |
| FT-PER-06 | Tags-Picker | API/UI | member | `GET …/personas/tags` liefert distinct Tags für Autocomplete. | |
| FT-PER-07 | Verlinkte Playbooks | UI | editor | Checkliste → Save (`PUT …/personas/{id}/playbooks`); Set-Replace-Semantik. | |
| FT-PER-08 | Versionshistorie | UI | member | `GET …/versions` + `…/versions/{v}`: Tabelle mit Status/Datum/Autor. | |
| FT-PER-09 | Diff | UI/API | member | `GET …/versions/{v}/diff?against=active` → strukturierter Feld-/Block-Diff. | |
| FT-PER-10 | Provenance | UI/API | member | `GET …/versions/{v}/provenance` → Status-Historie (wer/wann/warum aktiv). | |
| FT-PER-11 | Restore | UI/API | editor | `POST …/versions/{v}/restore` → neuer Draft (**201**), nicht-destruktiv. | |
| FT-PER-12 | Rendered | API | member | `GET …/personas/{id}/rendered` → Platzhalter/Pills expandiert. | |
| FT-PER-13 | Export JSON | UI/API | member | Export-Button bzw. `GET …/export?format=json` → Identität + alle Versionen. | |
| FT-PER-14 | Export Markdown | API | member | `…/export?format=markdown` → gerenderter Body der aktiven Version + YAML-Frontmatter. | |
| FT-PER-15 | Delete (frei) | UI | editor | Danger-Zone → Bestätigung → **204**, wenn **kein** Agent die Persona referenziert. | |
| FT-PER-16 | Delete blockiert | API | editor | Persona, die von Agent(en) referenziert wird, löschen → **409** `DeleteBlocked` mit `blocked_by`-Map (Persona←Agenten). | |

---

# E · Playbooks (inkl. Composite)

| ID | Ziel | Oberfläche | Rolle | Schritte / Erwartung | ✅ |
|----|------|-----------|-------|----------------------|----|
| FT-PB-01 | Liste + Filter | UI/API | member | `/playbooks`: Pagination; `GET …/playbooks?tag=…&trigger=…` filtert. | |
| FT-PB-02 | Anlegen mit Type | UI | editor | `/playbooks/new`: Type-Select (Prompt/Instructions/Snippet/Workflow/Checklist/FAQ) mit Hint, Sprache → **201**. | |
| FT-PB-03 | Edit Body (BlockNote) | UI | editor | Body mit BlockNote: Resource-/Playbook-/Catalog-Pills via Slash-Menü einfügen. | |
| FT-PB-04 | Triggers & Tags | UI | editor | Triggers (kommasepariert) + Multi-Tag-Input. Detail zeigt Trigger-Badges. | |
| FT-PB-05 | Tags-Endpoint | API | member | `GET …/playbooks/tags` distinct. | |
| FT-PB-06 | Triggers-Übersicht | API | member | `GET …/playbooks/triggers` → dedupliziert mit Playbook-Refs (Wave 5). | |
| FT-PB-07 | Resource-Links | API/UI | editor | `PUT …/playbooks/{id}/resource_links` (block_id, position, link_scope resource/block, embedding_mode lazy/inline). UI: LinkedBlocksList bzw. ResourceBlockLinkPicker. | |
| FT-PB-08 | Composite: composes | UI/API | editor | `PUT …/playbooks/{id}/composes` ordered child-set; Composite-Badge; leere Liste = nicht-composite (ADR-0024). | |
| FT-PB-09 | composed_by | UI/API | member | `GET …/composed_by` → Eltern-Playbooks. | |
| FT-PB-10 | „Used In" | UI | member | Detail zeigt Personas, die das Playbook nutzen. | |
| FT-PB-11 | Usages-Reverse | API | member | `GET …/playbooks/{id}/usages` → was referenziert es. | |
| FT-PB-12 | Versionen/Diff/Prov./Restore/Rendered | UI/API | member/editor | analog FT-PER-08…12. | |
| FT-PB-13 | Export JSON/MD | UI/API | member | analog FT-PER-13/14. | |
| FT-PB-14 | Delete blockiert | API | editor | Playbook, das Personas/Composites referenzieren → **409** `DeleteBlocked` (Playbook←Personas/Composites). Sonst **204**. | |

---

# F · Resources (inkl. Sub-Resources)

| ID | Ziel | Oberfläche | Rolle | Schritte / Erwartung | ✅ |
|----|------|-----------|-------|----------------------|----|
| FT-RES-01 | Liste + Tag-Filter | UI/API | member | `/resources`; `?tag=…`. | |
| FT-RES-02 | Anlegen + BlockNote | UI | editor | `/resources/new`: Name, Beschreibung, Tags, Body (BlockNote-Insel) → **201**. | |
| FT-RES-03 | StatusActionBar + Validierung | UI | editor/admin | Promote (Review→Active, admin): bei fehlenden Pflichtfeldern → **409**, Fehler nennt fehlende Felder. Submit/Reject/Reaktivieren vorhanden. | |
| FT-RES-04 | Sub-Resources | UI/API | editor | `PUT …/resources/{id}/sub_resources` ordered (block_id, position, scope, embedding_mode). UI: SubResourcePicker. | |
| FT-RES-05 | used_by | UI/API | member | `GET …/resources/{id}/used_by` → Eltern-Resources. „Linked In" zeigt Playbooks. | |
| FT-RES-06 | Usages-Reverse | API | member | `GET …/resources/{id}/usages`. | |
| FT-RES-07 | Versionen/Diff/Prov./Restore | UI/API | member/editor | analog FT-PER-08…11. | |
| FT-RES-08 | Tags-Endpoint | API | member | `GET …/resources/tags`. | |
| FT-RES-09 | Export JSON/MD | UI/API | member | analog FT-PER-13/14. | |
| FT-RES-10 | Delete blockiert | API | editor | Resource, deren Blocks Playbooks/Composites referenzieren → **409** `DeleteBlocked` (Resource←Playbooks/Composites). Sonst **204**. | |

---

# G · System-Prompt-Templates

| ID | Ziel | Oberfläche | Rolle | Schritte / Erwartung | ✅ |
|----|------|-----------|-------|----------------------|----|
| FT-SP-01 | Liste | UI/API | member | `/system-prompts`, Pagination. | |
| FT-SP-02 | Anlegen | UI | editor | `/system-prompts/new`: Name (Pflicht), Beschreibung, Body (BlockNote), Placeholder-Help-Link → **201**. | |
| FT-SP-03 | Edit → neue Version | API/UI | editor | `PUT …/system-prompts/{id}`: auf aktive Version → neuer Draft/Inactive. | |
| FT-SP-04 | Versionen/Diff/Prov. | UI/API | member | analog Versions-Strang. | |
| FT-SP-05 | Transition/Restore | UI/API | editor/admin | `POST …/versions/{v}/transition` + `…/restore`. | |
| FT-SP-06 | Placeholder-Hilfe | UI | member | `/help/placeholders` listet Platzhalter-Syntax mit Beispielen. | |

---

# H · Agenten (Konfiguration in der UI)

> Agenten sind **nicht versioniert** (Konfiguration). Sie bündeln Persona + System-Prompt-Template + Playbooks + Tool-Policy.

| ID | Ziel | Oberfläche | Rolle | Schritte / Erwartung | ✅ |
|----|------|-----------|-------|----------------------|----|
| FT-AG-01 | Liste + Status-Badge | UI/API | member | `/agents`: Name, „Incomplete"-Badge (wenn nicht aktivierbar), Status-Badge enabled/disabled. | |
| FT-AG-02 | Anlegen (inline) | UI | editor | „New Agent" → Default-Name; Persona-Select, Template-Select, Playbook-Links, Status. Viewer kann nicht anlegen. | |
| FT-AG-03 | Hierarchie-Ansicht | UI | member | AgentHierarchyView: Agent → Persona (Versions-Badge), Template (Versions-Badge), verlinkte Playbooks. | |
| FT-AG-04 | Enable-Guard | API | editor | `status=enabled` bei unvollständigem Agent (fehlende Persona/Template oder Persona ohne aktive Version) → **409**. | |
| FT-AG-05 | Render Prompt | API | member | `GET …/agents/{id}/render?format=plain\|markdown\|html` → kompilierter System-Prompt, Platzhalter aufgelöst. | |
| FT-AG-06 | Rendered (voll) | API | member | `GET …/agents/{id}/rendered` → Agent + Persona + expandierter Prompt. | |
| FT-AG-07 | Copy-Prompt-Button | UI | member | Nur bei `enabled` aktiv → kompilierter Prompt in Zwischenablage. | |
| FT-AG-08 | Duplizieren | UI/API | editor | `POST …/agents/{id}/copy` → Klon „… (Kopie)"; **409**, wenn Quelle nicht aktivierbar. | |
| FT-AG-09 | Tool-Policy setzen | UI/API | editor | `PUT …/agents/{id}` mit `tool_policy` (ReadScope all/assigned/none je Playbook/Resource; Read/Write-Flags; `promote_retire`). | |
| FT-AG-10 | Delete | UI/API | editor | `DELETE …/agents/{id}` → **204**. | |

---

# I · Versionierungs-State-Machine (Querschnitt D–G)

> Für **jede** Entität (Persona/Playbook/Resource/System-Prompt) einmal komplett durchspielen.

| ID | Ziel | Oberfläche | Rolle | Schritte / Erwartung | ✅ |
|----|------|-----------|-------|----------------------|----|
| FT-VER-01 | Submit | UI/API | editor | `transition to=review`: draft→review. BranchStatus „Submit". | |
| FT-VER-02 | Publish | UI/API | admin | review→active. Als editor → **403**. | |
| FT-VER-03 | Reject | UI/API | editor | review→draft. | |
| FT-VER-04 | Retire | UI/API | admin | active→inactive. Als editor → **403**. | |
| FT-VER-05 | Reset | UI/API | admin | active→draft. Jeder Übergang **ab `active`** ist admin-only (ADR-0023); als editor → **403**. | |
| FT-VER-06 | Reaktivieren | UI/API | editor | inactive→draft („Reaktivieren als Draft"). | |
| FT-VER-07 | PUT-auf-Active = Draft | API | editor | PUT auf aktive Version erzeugt neuen Draft. | |
| FT-VER-08 | Draft-Konflikt | API | editor | PUT/Update bei bereits existierendem Draft → **409**. | |
| FT-VER-09 | Unique-Active-Invariante | API | admin | Es kann pro Aggregat nur **eine** aktive Version geben (partial-unique-index hält). | |
| FT-VER-10 | Transition-Note | API | editor | `note` (≤2000 Zeichen) erscheint in Provenance. | |

---

# J · Verlinkung, Pills & Platzhalter (Querschnitt)

| ID | Ziel | Oberfläche | Rolle | Schritte / Erwartung | ✅ |
|----|------|-----------|-------|----------------------|----|
| FT-LINK-01 | Persona↔Playbook | UI/API | editor | Set-Replace; Backlink „Used In". | |
| FT-LINK-02 | Playbook↔Resource (Block-Ref) | UI/API | editor | Section-aware Block-Ref (Heading-Anker/Section-Slice); inline vs. lazy embedding. | |
| FT-LINK-03 | Playbook↔Playbook (Composite) | UI/API | editor | geordnete Sequenz; composed_by-Backlink. | |
| FT-LINK-04 | Resource↔Resource (Sub) | UI/API | editor | geordnet; used_by-Backlink. | |
| FT-LINK-05 | Pill-Preview-Overlay | API/UI | member | `GET …/placeholders/preview?kind=…&target_id=…&persona_id=…` → aufgelöster Pill-Output (Klick-Overlay im Editor). | |
| FT-LINK-06 | Applied-via-Pill | UI | member | Pills in BlockNote-Bodies sind klickbar (Preview/Navigieren). | |

---

# K · Dashboard

| ID | Ziel | Oberfläche | Rolle | Schritte / Erwartung | ✅ |
|----|------|-----------|-------|----------------------|----|
| FT-DASH-01 | KPIs | UI | member | Aktive Personas/Playbooks, „Pending Reviews". | |
| FT-DASH-02 | Status-Verteilung | UI | member | StatusDonut je Entität (draft/review/active/inactive) + Legende. | |
| FT-DASH-03 | Activity-Feed | UI/API | member | `GET …/dashboard?page=&page_size=` (1–100), paginiert; Klick navigiert zur Entität. Empty-State. | |

---

# L · API-Tokens & Agent-Binding

| ID | Ziel | Oberfläche | Rolle | Schritte / Erwartung | ✅ |
|----|------|-----------|-------|----------------------|----|
| FT-TOK-01 | Token anlegen | UI/API | editor | `POST …/tokens`: Name; optional Rollen-Override (≤ eigene Rolle); optional Agent-Binding. Klartext-Token **einmalig** sichtbar. viewer → **403** (`token_service.py` `require_role(editor)`, konsistent mit ADR-0023). | |
| FT-TOK-02 | Liste | UI/API | member | Name, Created, Last-used, Revoked; Tail maskiert („…xyz"). | |
| FT-TOK-03 | Revoke | UI/API | editor | `DELETE …/tokens/{id}` → **204**, sofort ungültig. viewer → **403**. | |
| FT-TOK-04 | Workspace-Pinning | API | — | Token gilt nur für seinen Workspace; Cross-Workspace-Aufruf scheitert. | |
| FT-TOK-05 | Rollen-Snapshot | API | — | Token trägt Rolle als Snapshot (ADR-0023); spätere Downgrades wirken. | |
| FT-TOK-06 | Override-Laden | UI | member | Token aus Datei einfügen → „Activate" → Konfiguration geladen. | |

---

# M · i18n / Locale

| ID | Ziel | Oberfläche | Rolle | Schritte / Erwartung | ✅ |
|----|------|-----------|-------|----------------------|----|
| FT-I18N-01 | UI-Sprache | UI | auth | Language-Switcher (Header & Account) → komplette UI übersetzt, persistiert (localStorage). | |
| FT-I18N-02 | Content-Locale | UI/API | editor | Anlegen mit Sprachauswahl; `?locale=` bei GETs liefert lokalisierten Content. | |
| FT-I18N-03 | Fallback | API | member | Nicht vorhandene Locale → definierter Fallback (kein 500). | |

---

# N · Account-Lifecycle, GDPR & Sicherheit (User-Self-Service)

| ID | Ziel | Oberfläche | Rolle | Schritte / Erwartung | ✅ |
|----|------|-----------|-------|----------------------|----|
| FT-ACC-01 | Anzeigename | UI | auth | Account → Display-Name ändern. | |
| FT-ACC-02 | Email ändern | UI | auth | ChangeEmailForm → Re-Confirmation-Mail; Email erst nach Bestätigung aktiv. | |
| FT-ACC-03 | Passwort ändern | UI | auth | Aktuelles + neues (≥8) + Bestätigung. | |
| FT-ACC-04 | MFA | UI | auth | MFA aktivieren → Backup-Codes anzeigen; deaktivieren. (Admin-MFA siehe `docs/mfa-admin.md`.) | |
| FT-ACC-05 | Überall abmelden | UI | auth | „Sign out everywhere" beendet alle Sessions. | |
| FT-ACC-06 | Theme | UI | auth | Light/Dark-Toggle, persistiert. | |
| FT-ACC-07 | Daten-Export | UI/API | auth | DataExportSection bzw. `GET /v1/gdpr/export` → alle User-Daten über alle Workspaces (Art. 20). | |
| FT-ACC-08 | Account löschen | UI/API | auth | DeleteAccountSection bzw. `DELETE /v1/me` → Soft-Delete, 30-Tage-Frist → **204**. | |
| FT-ACC-09 | Rate-Limits | API | auth | Mutierende Endpoints wiederholt feuern → **429** (Limiter greift). | |

---

# O · Billing / Entitlement (sofern Edition aktiv)

| ID | Ziel | Oberfläche | Rolle | Schritte / Erwartung | ✅ |
|----|------|-----------|-------|----------------------|----|
| FT-BIL-01 | Entitlement-Snapshot | API | member | `GET …/billing/entitlement` → Org-Entitlement + aktuelle MCP-Nutzung. Workspace ohne Org → **403**. | |
| FT-BIL-02 | On-Prem-Lizenz | — | — | On-Prem: Entitlement nur aus K_pub-verifiziertem `WHO2BE_LICENSE_KEY` (kein Tabellen-Write). | |

---

# P · Agenten-Reise über MCP — Read-Tools

> Token mit passender Policy nötig (siehe Strang L). **Alle Reads sehen nur `status='active'`.**

| ID | Ziel | Tool | Erwartung | ✅ |
|----|------|------|-----------|----|
| FT-MCPR-01 | Persona laden | `get_persona(identifier, locale)` | UUID **oder** Name; liefert Persona + verlinkte Playbooks + `body_rendered` (Pills/Slash-Refs aufgelöst). Nur aktive Version. | |
| FT-MCPR-02 | Playbooks listen | `list_playbooks(tag?, trigger?, locale)` | nur aktive; Filter wirken. | |
| FT-MCPR-03 | Trigger-Discovery | `list_triggers()` | deduplizierte Trigger + Playbook-Refs (id+name). | |
| FT-MCPR-04 | Playbook holen | `fetch_playbook(id, locale)` | Resource-Links: `inline` voll eingebettet, `lazy` als Pointer; Sub-Playbooks (1 Ebene); `body_rendered`. | |
| FT-MCPR-05 | Resources listen | `list_resources(tag?, locale)` | aktive; Tag exakt/case-sensitiv. | |
| FT-MCPR-06 | Resource holen | `fetch_resource(id, block_ids?, locale)` | optionale Block-Auswahl; `sub_resources` (Pointer) + `inline_sub_resources` (1 Ebene). | |
| FT-MCPR-07 | Agent holen | `fetch_agent(id)` | Agent + Persona (aktiv) + `system_prompt_rendered` (alle Platzhalter aufgelöst). | |
| FT-MCPR-08 | Sichtbarkeits-Test | alle Reads | Draft/Review/Inactive **nicht** sichtbar. Entität auf inactive setzen → verschwindet aus MCP-Reads. | |

---

# Q · Agenten-Reise über MCP — Write-Tools (ADR-0030)

> Schreibende Tools brauchen `*_write` (= editor serverseitig); Promote/Retire = admin. **Kein Delete, kein Export über MCP.**

| ID | Ziel | Tool | Erwartung | ✅ |
|----|------|------|-----------|----|
| FT-MCPW-01 | Persona anlegen | `create_persona` | Draft v1; **unsichtbar** für Reads bis `transition_persona(...,to='active')`. | |
| FT-MCPW-02 | Persona updaten | `update_persona` | neuer Draft aus active; **409** wenn Draft existiert. | |
| FT-MCPW-03 | Persona transitionieren | `transition_persona(version,to,note?)` | State-Machine; →active/→inactive nur admin. | |
| FT-MCPW-04 | Persona restore | `restore_persona(version)` | alte Version → neuer Draft. | |
| FT-MCPW-05 | Persona-Playbooks | `set_persona_playbooks(ids)` | Set-Replace; leere Liste löst Links. | |
| FT-MCPW-06 | Playbook-Set | `create/update/transition/restore_playbook` | analog Persona. | |
| FT-MCPW-07 | Resource-Links | `set_playbook_resource_links(links)` | scope/embedding/block_id korrekt. | |
| FT-MCPW-08 | Composite-Set | `set_playbook_composes(child_ids)` | geordnet; leer = nicht-composite. | |
| FT-MCPW-09 | Resource-Set | `create/update/transition/restore_resource` | analog. | |
| FT-MCPW-10 | Sub-Resources | `set_resource_sub_resources(links)` | geordnet, scope/embedding. | |
| FT-MCPW-11 | Agent anlegen | `create_agent` | startet `disabled` (oder spezifiziert); **409** bei enabled+unvollständig. | |
| FT-MCPW-12 | Agent updaten | `update_agent` | nur gesetzte Felder ändern; `tool_policy` setzbar. | |
| FT-MCPW-13 | Agent kopieren | `copy_agent(name?)` | Klon; **409** wenn Quelle nicht aktivierbar. | |
| FT-MCPW-14 | Kein Delete/Export | — | Es existieren **keine** `delete_*`/`export_*`-Tools (verifizieren). | |

---

# R · MCP-Autorisierung & Per-Agent-Tool-Policy

| ID | Ziel | Oberfläche | Erwartung | ✅ |
|----|------|-----------|-----------|----|
| FT-POL-01 | Editor-Gate | MCP | Write-Tool mit nicht-editor-Token → **403** (serverseitig, `ToolError`). | |
| FT-POL-02 | Admin-Gate | MCP | Promote/Retire mit nur-editor-Token → **403**. | |
| FT-POL-03 | ReadScope | MCP | Token an Agent mit `playbook_read=assigned` → nur zugeordnete Playbooks sichtbar; `none` → keine. | |
| FT-POL-04 | Capability-Flag | MCP | Agent-Policy ohne `persona_write` → `create/update_persona` → **403**. | |
| FT-POL-05 | Agent-gebundenes Token | MCP | Token mit Agent-Binding erbt dessen Tool-Policy; Versuch außerhalb der Policy → **403** mit Detail. | |
| FT-POL-06 | Ungültiges Token | MCP | Kein/abgelaufenes/widerrufenes Token → **401**. | |

---

# S · Negativ-, Grenz- & Sicherheitsfälle (Querschnitt)

| ID | Ziel | Oberfläche | Erwartung | ✅ |
|----|------|-----------|-----------|----|
| FT-NEG-01 | DeleteBlocked-Body | API | 409 enthält `message` + `blocked_by`-Map; kein Cascade auf fremde Aggregate. | |
| FT-NEG-02 | Draft-Konflikt | API | zweiter paralleler Edit → **409**, Hinweis „bestehenden Draft weiterbearbeiten". | |
| FT-NEG-03 | Cross-Tenant | API | Zugriff auf fremden Workspace/Entität → **403/404**. | |
| FT-NEG-04 | Open-Redirect | UI | `next`/`redirect_to` nur intern. | |
| FT-NEG-05 | Email-Mismatch (Invite) | UI/API | falscher User → Annahme verweigert. | |
| FT-NEG-06 | Rate-Limit | API | **429** bei Burst auf Writes. | |
| FT-NEG-07 | Editor-load-Spurious-PATCH | UI | BlockNote ignoriert ersten onChange beim Laden → **kein** ungewollter Draft-PATCH. | |
| FT-NEG-08 | 404 sauber | API/UI | Unbekannte ID → **404**, kein 500. | |
| FT-NEG-09 | Security-Header | — | (Prod) Caddy setzt HSTS/X-CTO/X-Frame/Referrer/Permissions + CSP; lokaler nginx **keine** Header. | |

---

# T · Rollen-Abnahme-Matrix

> Jede Zeile als **viewer**, **editor**, **admin** durchspielen. Erwartung pro Rolle:

| Aktion | viewer | editor | admin | ✅ |
|--------|:------:|:------:|:-----:|----|
| Lesen (Listen/Detail/Versionen/Diff/Provenance/Export) | ✓ | ✓ | ✓ | |
| Create/Update (Persona/Playbook/Resource/SP/Agent) | ✗ (403/UI gesperrt) | ✓ | ✓ | |
| Submit/Reject/Reaktivieren (editor-Transitionen) | ✗ | ✓ | ✓ | |
| Publish (→active) / Retire (→inactive) / Reset (active→draft) | ✗ | ✗ (403) | ✓ | |
| Delete (Persona/Playbook/Resource/Agent) | ✗ | ✓ | ✓ | |
| Links/Composes/Sub-Resources setzen | ✗ | ✓ | ✓ | |
| Mitglieder/Einladungen/Rollen verwalten | ✗ | ✗ | ✓ | |
| Workspace/Org umbenennen & löschen | ✗ | ✗ | ✓ (Org-Delete: owner) | |
| Tokens anlegen/widerrufen | ✗ (403) | ✓ (≤ eigene Rolle) | ✓ | |

---

## Empfohlene Durchlauf-Reihenfolge (End-to-End-Pfad)

1. **Setup:** Strang 0 → A (Signup/Login) → B (Org+Workspace) → C (3 Rollen einladen).
2. **Content-Aufbau:** F (Resource) → E (Playbook, verlinkt Resource) → D (Persona, verlinkt Playbook) → G (System-Prompt) → H (Agent aus Persona+Template+Playbooks).
3. **Lifecycle:** I (komplette State-Machine je Entität) → J (Links/Pills) → K (Dashboard spiegelt Status).
4. **Agenten:** L (Token + Agent-Binding) → P (Reads) → Q (Writes) → R (Policy-Gates).
5. **Self-Service & Edge:** M (i18n) → N (Account/GDPR/MFA) → O (Billing) → S (Negativfälle) → T (Rollen-Matrix).

> **Hinweis zur Aktualität:** Dieser Plan deckt den Code-Stand 2026-06-09 ab und geht über das
> CLAUDE.md-Changelog hinaus (zusätzlich enthalten: System-Prompt-Templates, GDPR-Export,
> Account-/Org-Lifecycle, MFA, Per-Agent-Tool-Policy, i18n/Locale, Pill-Preview-Overlay).
> Bei jedem neuen Feature-Block einen passenden Test-Strang ergänzen.
