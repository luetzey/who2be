# Feature-Expansion: Editionen, Spaces, Versionierung, Resources, Persona-Pills, Agenten, Dashboard

**Status:** Plan (Brainstorming abgeschlossen, Entscheidungen final) — bereit zur Verteilung
**Datum:** 2026-06-02
**Integrations-Branch:** `claude/intelligent-gauss-u6Cia`
**Methode:** Orchestrator-Fan-out — 8 datei-disjunkte Tracks in 3 Wellen, je eigener `feat/`-Branch + eigener Draft-PR.

> Dieses Dokument ist das Living Document der Coder-Methode (Phase 1). Es hält
> alle Brainstorming-Entscheidungen, die Track-Aufteilung und die fertigen
> Handoff-Prompts. Notion bekommt nur einen kurzen Pointer in der Projekt-`## Notes`.

---

## 1. Entscheidungs-Ledger (12 Forks, final)

| # | Thema | Entscheidung |
|---|---|---|
| 1 | Edition | Ein Build + `WHO2BE_EDITION=cloud\|onprem`-Runtime-Flag + Entitlement-Layer. On-Prem unbegrenzt & ohne Billing-UI; Cloud erzwingt Org-Limits + Billing. |
| 2 | Spaces/Billing | **Org** = Billing/Plan/Limits/Mitglieder · **User** = Konto (Profil/Security/Prefs, blendet Solo-Org-Rechnung ein) · **Workspace** = Settings/Mitglieder/Danger-Zone. Alle drei jetzt. (Konsistent mit ADR-0019.) |
| 3 | Rollen | `admin > editor > viewer` bleiben. **Nur UI verdrahten** (Promote/Demote, Sperren, Einladen). Kein Reviewer/Owner, keine neuen Rollen-Migrationen. |
| 4 | Versionierung | **Non-destruktiv.** „Version N wiederherstellen" → neuer Draft aus Snapshot N. Diff-gegen-aktiv. „warum aktiv"-Provenance aus `status_history`. Reset einer aktiven Version auf Draft reaktiviert automatisch die zuletzt aktive (immer genau eine aktiv, DB-Invarianten bleiben). |
| 5 | Resource-Tiefe | Resource→Resource-Refs, unendliche Tiefe, azyklischer Recursive-Check (wie `playbook_composition`). |
| 6 | `fetch_resource`-Vertrag | Eigener Body **inline** + Tabelle der **direkten** Sub-Resources (je Zeile: child-id, name, fertige `fetch_resource('<id>')`-Anweisung). Kinder-Inhalt wird **nicht** expandiert. |
| 7 | Persona-Pills | Voller Pill-Satz wie System-Prompt: Slash-Refs auf einzelne Playbooks/Resources + Katalog-Pills `playbooks-catalog` (all\|triggered) + `resources-catalog` (all\|tag) + Skills-Tabelle. Alles fetch-time-dynamisch via MCP. |
| 8 | Skills | Leichte Refs `{name, note}` an der Persona, gerendert als Tabelle (Skill \| Beschreibung \| Hinweis). Keine neue Entität. |
| 9 | Cloud-Limit | MCP-**Monatskontingent pro Org** (Usage-Tabelle, Monats-Reset) + per-Token-**Rate-Ceiling** (req/min, slowapi), **aus dem Org-Entitlement (SSoT)** gelesen. On-Prem unbegrenzt. Gilt nur für agent-facing Reads. Architektur: §3.5/§3.6. |
| 10 | On-Prem-Admin | Env-seeded: `WHO2BE_BOOTSTRAP_ADMIN_EMAIL` (+ Magic-Link/Initialpasswort beim ersten Boot) → Org-Owner + Workspace-Admin deterministisch. |
| 11 | BlockNote | `body_format='plain'`-Pfad **raus**; alles BlockNote. **Markdown-aware** Migration der Altbestände (Headings/Listen/Code), Fallback Paragraph. |
| 12 | Placeholder-Hinweis | Dauer-Hinweis „verfügbare Placeholder" → kompaktes Info-Button/Popover (+ Doku-Link). |

### Defaults (Veto möglich, sonst gültig)
- **Dashboard:** Status-Verteilung als Donut/Bar (CSS/SVG, **keine** neue Chart-Dependency), KPIs visueller, **Activity nach ganz unten**, **seitenbasierte Pagination** (20/Seite).
- **Agenten:** `persona_id` + `system_prompt_template_id` optional (leere Hülle), `POST /agents/{id}/copy`, **Copy gesperrt bei unvollständiger Hülle**.
- **MCP-Limit** trifft nur agent-facing Reads (`get_persona`, `list/fetch_playbook`, `list/fetch_resource`, `fetch_agent`/render), nicht die Operator-/Web-Reads.

---

## 2. Track-Map · Wellen · Merge-Reihenfolge

**Welle 1 — Fundament** — **Ausführung: EIN Agent macht A→B sequentiell** (A committen/mergen, dann B), weil sich A und B die Model-Dateien `playbook.py`/`system_prompt_template.py` teilen (A nur Status-/Versions-Felder, B nur `body_format`/Content). So entstehen keine Kollisionen.
- **A** Versionierung-Core
- **B** Nur-BlockNote + Migration + Placeholder-Popover

**Welle 2 — voll parallel** (disjunkt, nach Welle 1)
- **C** Tenancy/Spaces/Workspace-Mgmt/Rollen-UI
- **D** Editionen/Entitlement/MCP-Limits/On-Prem-Bootstrap
- **G** Dashboard-Viz + Pagination
- **H** Agenten (Delete-UI, leere Hülle, Copy-Sperre)

**Welle 3 — parallel** (nach B+D gemerged; E und F disjunkt zueinander)
- **E** Resource-Composition + MCP-Stub
- **F** Persona-Pills + Skills-Tabelle

**Invariante:** innerhalb einer Welle teilen sich keine zwei Tracks eine Datei. Über Wellen hinweg gilt die obige Merge-Reihenfolge; spätere Wellen rebasen auf den gemergten Stand.

---

## 3. Cross-Cutting-Verträge (für alle Tracks verbindlich)

### 3.1 Versionierungs-Modell (Track A definiert, alle Reads/UI nutzen)
- `status.py`: bestehende State-Machine bleibt; `inactive → draft` bleibt „Reaktivieren".
- **Restore:** `POST .../{id}/versions/{n}/restore` → liest Snapshot `n`, validiert *strict* (ADR-0009), schreibt ihn als **neue Draft-Version** (kein Pointer-Reset). 409 falls bereits ein Draft offen ist (konsistent mit PUT-auf-Active).
- **Reset-auf-Draft:** Transition `active → draft` einer Version reaktiviert die **zuletzt aktive** Version (jüngste `status_history`-`active`-Episode), damit die Invariante „genau eine aktiv" hält. Wenn es keine vorherige aktive gibt → Entität ohne aktive Version (erlaubt).
- **Diff:** `GET .../{id}/versions/{n}/diff?against=active` → strukturierter Block-/Feld-Diff (serverseitig berechnet, JSON). UI rendert ihn read-only.
- **Provenance:** `GET .../{id}/versions/{n}/provenance` → die `status_history`-Kette dieser Version (wer/wann/von→nach + note). Beantwortet „warum aktiv".

### 3.2 Nur-BlockNote (Track B)
- `body_format` aus `playbook.py`, `system_prompt_template.py` Models + DB entfernen; Content ist immer BlockNote-JSON.
- Migration `0029_*`: alle `…_version.content` mit altem `plain`-Body markdown-aware nach BlockNote-Blöcken konvertieren (Headings, Listen, Code-Fences, Absätze; Rest → Paragraph). Idempotent, mit `schema_migrations`-Eintrag.
- MCP/Agent-Render liest nur noch BlockNote; `body_rendered` expandiert Pills weiterhin.
- Editor startet direkt als BlockNote; „Zu BlockNote konvertieren"-Affordance entfernt; Placeholder-Hinweis → Popover.

### 3.3 Resource-Composition + MCP-Stub (Track E)
- Sub-Resource-Link analog `playbook_resource_link` (`link_scope` resource/block), **mit azyklischem Recursive-CTE-Check** vor Insert.
- `fetch_resource(id)`: liefert **eigenen** Body + Feld `sub_resources: [{id, name, link_scope, block_id?, fetch_call: "fetch_resource('<id>')"}]`. **Keine** Expansion der Kinder.

### 3.4 Persona-Pills (Track F) — baut auf 3.2
- Wiederverwendung der System-Prompt-Pill-Maschinerie im Persona-BlockNote-Body: Slash-Refs (playbook/resource), `playbooks-catalog` (all\|triggered), `resources-catalog` (all\|tag).
- Skills-Tabelle aus `PersonaVersionContent.skills` (Track F rendert sie; Datenmodell bleibt `SkillRef{name,note}`).
- `get_persona` rendert Katalog-Pills fetch-time gegen die aktiven Playbooks/Resources des Workspace.

### 3.5 Edition + Entitlements + MCP-Limit (Track D) — nach Notion-Vault-Standards
**Leitprinzip (Licensing-Standards):** *Das Nutzungsrecht entscheidet die App über
Entitlements — der Zahlungsanbieter meldet nur Ereignisse, er steuert den Zugriff nicht.*

- **Entitlement = Single Source of Truth pro Org:** persistierte Struktur je Org
  `{status: active|inactive, features: set[str], expires_at, mcp_monthly_quota,
  mcp_rate_per_min}`. Jede gated Feature-/Read-Abfrage prüft erst das Entitlement.
  Default `OSS_ENTITLEMENT` (unbegrenzt, alle Features) für On-Prem/OSS.
- **Hexagonal (Deployment-Standards): `EntitlementPort` + zwei Adapter.** Der Kern
  liest nur das aufgelöste Entitlement; die Herkunft ist ein austauschbarer Adapter:
  - **Cloud-Adapter (webhook-getrieben):** Stripe/Mollie ist führend für den
    Zahlungsstatus und sendet Webhooks → Signatur **immer** gegen Provider-Secret
    verifizieren → Produkt→Feature-Mapping über Provider-Metadaten
    (`license_policy`/`short_code`, kein hartkodiertes Mapping) → Org-Entitlement
    setzen (`active`/Features/Laufzeit). Kündigung/Fehlzahlung → sofort entzogen.
  - **On-Prem-Adapter (offline):** signierte Lizenzdatei, verifiziert mit `K_pub`
    (Ed25519, nur Public-Key im Repo) — **kein** Phone-Home. `WHO2BE_LICENSE_KEY`.
    Deckt sich mit `…0528_enterprise-license-management`.
- **Billing-Integration ist ein Cloud-Adapter, nicht im Kern.** Das gesamte
  Stripe/Webhook-Modul wird nur unter `is_cloud()` aktiviert; OSS/On-Prem nie.
- **MCP-Limit liest aus dem Entitlement:** Monatskontingent
  (`mcp_usage(org_id, period_yyyymm, count)`, 429 bei Überschreitung) + per-Token-
  Rate (slowapi). Quota/Rate kommen aus dem Org-Entitlement. Nur agent-facing Reads.
- **Config strikt vom Code (12-Factor III):** Edition, Lizenz-Key, Provider-Secrets
  via Env; `.env` gitignored; nur `K_pub` im Repo, **nie** der Private-Key.
- **On-Prem-Bootstrap:** Lifespan-Start, kein User + `WHO2BE_BOOTSTRAP_ADMIN_EMAIL`
  → Admin + Personal-Org + Workspace seeden.

### 3.6 Deployment- & Licensing-Standards (Notion-Vault — verbindlich)
Quelle: Playbooks *Deployment-Standards (Single Codebase)* (`373be537-2ab8-8133-9a6a-c6d2babde6cb`)
+ *Licensing-Standards (Entitlements)* (`373be537-2ab8-81fc-944e-ed1d41b8e82b`).
Gelten als Constraints für **alle** Tracks mit Edition-/Tenancy-/Cloud-Bezug (v. a. C, D):

- **Single Codebase, kein Fork** — Umgebungsunterschiede in Config + Adaptern,
  nicht in parallelen Codebasen. (= Entscheidung #1.)
- **Hexagonal (Ports & Adapters):** Geschäftslogik von Infra isolieren; cloud-
  spezifische Dinge (Billing, Mailer, Storage) als Adapter hinter Ports, Kern unverändert.
- **Ein unveränderliches Docker-Artefakt** für beide Targets (build-once-deploy-
  anywhere); Edition nur per Laufzeit-Config.
- **DB-Symmetrie:** ein Schema für Cloud + On-Prem mit `organization_id`/
  `workspace_id`. **Cloud-Defense-in-Depth (additiv): Postgres RLS** mit Mandanten-
  Kontext pro Request; On-Prem identisches Schema, RLS deaktiviert/per System-ID
  umgangen — **ohne** den App-SQL zu ändern. Heute: app-seitiges `WHERE workspace_id`
  (ADR-0019). RLS ist eine empfohlene Cloud-Härtung → eigener Hardening-Schritt
  (siehe §5), nicht verstreut im Kern-SQL.
- **Logs als Event-Stream** (stdout/stderr) — bereits via structlog erfüllt.

**Anti-Patterns (verbindliche Guardrails):**
- Zugriff am Zahlungsstatus statt am Entitlement festmachen.
- Webhooks ohne Signaturprüfung verarbeiten.
- On-Prem-Lizenzprüfung mit Online-Call.
- Privaten Signing-Key im Repo (nur `K_pub`).
- Billing-Logik im Anwendungskern.
- Getrennte Repos / pro Umgebung ein eigenes Image / getrenntes DB-Schema.

---

## 4. Handoff-Prompts (autonom verwendbar)

> Jeder Prompt ist für einen frischen Claude-Code-Agenten gedacht. Branch- und
> DoD-Block sind identisch; nur Scope unterscheidet sich. **DoD (alle Tracks):**
> betroffener Stack grün — Python: `uv run ruff check . && uv run mypy . && uv run pytest -q`;
> Web: `npm run lint && npx tsc --noEmit && npm test && npm run build`.
> Bugfix = erst reproduzierender failing Test. Security-sensible Stellen (Auth, DB,
> MCP, externe Inputs) mit `security-reviewer`-Subagent prüfen. Conventional
> Commits, Draft-PR, **nicht** in `main`/Integrations-Branch pushen.

> **Welle-1-Ausführung:** Tracks A und B werden von **einem** Agenten nacheinander
> umgesetzt (A → committen/mergen → B). Beide Prompts unten verweisen auf §3.

### Track A — Versionierung-Core (Welle 1, zuerst)
```
Branch: feat/versioning-restore-diff-provenance
Ziel: Non-destruktives Versionsmanagement für persona, playbook, resource,
system_prompt_template.

Kontext: Versionierung läuft über History-Tabellen (ADR-0004) mit Status pro
Version (draft/review/active/inactive, status.py + partial-unique-indices).
Transition-Endpoints existieren je Entität. Es gibt KEIN Restore/Diff/Provenance.

Implementiere (für ALLE VIER versionierten Entitäten):
1. POST .../{id}/versions/{n}/restore — Snapshot n strict validieren (ADR-0009)
   und als neue Draft-Version schreiben. 409 wenn bereits ein Draft offen.
2. Reset-auf-Draft: bei Transition active→draft die zuletzt aktive Version
   (jüngste status_history-active-Episode) reaktivieren, damit "genau eine aktiv"
   hält. Keine vorherige aktive → Entität ohne aktive Version.
3. GET .../{id}/versions/{n}/diff?against=active — strukturierter Block/Feld-Diff
   als JSON (serverseitig).
4. GET .../{id}/versions/{n}/provenance — status_history-Kette dieser Version.
5. Geteilte Web-Komponenten unter components/data/ oder components/version/:
   VersionHistory (Liste mit Status-Badges + Restore-Action + "warum aktiv"),
   VersionDiff (read-only Diff-View), Provenance. In allen vier Detail-Pages
   einhängen (PersonaDetailPage, PlaybookDetailPage, ResourceDetailPage,
   TemplateDetailPage).

DATEIEN (nur diese): status.py; *_service.py + *_repo.py der vier Entitäten
(nur Versions-/Status-Methoden, KEINE body_format/content-Schema-Änderung);
personas.py/playbooks.py/resources.py/system_prompts.py Router (nur neue
restore/diff/provenance-Routen anhängen); neue Web-Komponenten + Detail-Pages.
NICHT anfassen: body_format, Editor-Komponenten, MCP-Server, Pill-Logik.

Out of Scope: alles Nicht-Versionierungs-bezogene.
```

### Track B — Nur-BlockNote + Migration + Placeholder-Popover (Welle 1, nach A)
```
Branch: feat/blocknote-only-migration
Ziel: body_format='plain' vollständig entfernen; alles ist BlockNote; Altbestände
markdown-aware migrieren; Placeholder-Dauerhinweis → Popover.

Implementiere:
1. body_format aus packages/models (playbook.py, system_prompt_template.py) +
   aus DB entfernen. Content ist immer BlockNote-JSON.
2. Migration 0029_blocknote_only.sql: alle …_version.content mit altem
   plain-Body markdown-aware nach BlockNote-Blöcken konvertieren (Headings,
   Listen, Code-Fences; Rest Paragraph). Idempotent.
3. MCP/Agent-Render-Pfad (apps/mcp/server.py + AgentRenderService) auf
   Nur-BlockNote umstellen; body_rendered expandiert Pills weiterhin.
4. Web: BlockNoteEditor + Editor-Forms starten direkt als BlockNote; "Zu
   BlockNote konvertieren"-Affordance entfernen.
5. Placeholder-Hinweis (verfügbare Placeholder) → Info-Button + Popover, plus
   Link auf eine Doku-Seite (docs/ oder /help-Route).

DATEIEN: playbook.py, system_prompt_template.py (body_format-Felder); neue
Migration 0029; apps/mcp/server.py + Render-Service; apps/web Editor-Komponenten
+ EditorForms + Placeholder-Hinweis-Komponente.
NICHT anfassen: Versionierungs-Endpoints/Services (Track A), Persona-Pills
(Track F), Resource-Composition (Track E).

WICHTIG: Erst auf den gemergten Stand von Track A rebasen.
```

### Track C — Tenancy/Spaces/Workspace-Mgmt/Rollen-UI (Welle 2)
```
Branch: feat/spaces-workspace-management
Ziel: Org-/User-/Workspace-Space-Verwaltung + Fix für toten "Workspace
hinzufügen"-Button + Rollen-UI (Promote/Demote/Sperren/Einladen). Rollen bleiben
admin>editor>viewer (KEINE neuen Rollen, keine Migration).

Implementiere:
1. Bug: "Workspace hinzufügen" verdrahten → POST /organizations/{id}/workspaces.
2. Workspace-Mgmt-UI: umbenennen (PATCH), Mitglieder listen/Rolle ändern/entfernen
   (members-Router), einladen (invitations-Router), Workspace löschen (+ nötige
   DELETE-Route falls fehlt), Danger-Zone.
3. Drei Spaces als settings-Feature: User-Space (Profil/Security/Prefs),
   Org-Space (Mitglieder/Workspaces/Org-Settings — Billing-Tab als leerer Slot,
   den Track D füllt), Workspace-Space (Settings/Mitglieder/Danger).
4. Rollen-UI: Promote/Demote-Aktionen (admin-only), Hinweis "bestehende Token
   widerrufen" bei Downgrade (ADR-0023).

DATEIEN: organizations.py, workspaces.py, members.py, invitations.py Router
(nur Mgmt-Routen, KEINE Limit-Checks); apps/web/src/features/settings/** + neue
org/user-Settings-Pages + AppShell-Nav-Einträge.
NICHT anfassen: licensing/, Billing-Logik (Track D), Entity-Editoren.
```

### Track D — Editionen/Entitlements/MCP-Limits/On-Prem-Bootstrap (Welle 2)
```
Branch: feat/editions-entitlements-mcp-limits
Ziel: Cloud-vs-On-Prem über ein Runtime-Flag; Entitlement-Schicht als Single
Source of Truth pro Org (hexagonal, zwei Adapter); MCP-Request-Limitierung aus
dem Entitlement; On-Prem-Admin-Seed.
ZWINGEND nach §3.5 + §3.6 (Notion-Vault-Standards: Deployment + Licensing).

Implementiere:
1. WHO2BE_EDITION in core/config.py (12-Factor: nur Env); licensing/edition.py
   mit is_cloud().
2. Entitlement als Org-SSoT: licensing/entitlement.py
   Entitlement{status, features, expires_at, mcp_monthly_quota, mcp_rate_per_min};
   Default OSS_ENTITLEMENT (unbegrenzt). Persistenz pro Org (Migration:
   org_entitlement). Jede gated Abfrage prüft das Entitlement.
3. Hexagonal EntitlementPort + zwei Adapter (Kern liest nur das aufgelöste
   Entitlement, nie den Adapter):
   - Cloud (webhook): POST /v1/billing/webhook — Provider-Signatur IMMER gegen
     Provider-Secret (Env) verifizieren; Produkt→Feature-Mapping über Provider-
     Metadaten (license_policy/short_code), KEIN hartkodiertes Mapping; Org-
     Entitlement setzen (active/Features/Laufzeit), Kündigung→entzogen.
   - On-Prem (offline): WHO2BE_LICENSE_KEY = signierte Lizenzdatei, verifiziert
     mit licensing/keys/ K_pub (Ed25519, NUR Public-Key; heute .gitkeep). Kein
     Phone-Home.
4. MCP-Limit-Gate NUR für agent-facing Reads (get_persona, list/fetch_playbook,
   list/fetch_resource, fetch_agent/render): mcp_usage(org_id, period_yyyymm,
   count) inkrementieren + 429 bei Quota; per-Token-Rate via core/rate_limit.py.
   Quota/Rate stammen aus dem Org-Entitlement. Nur aktiv wenn is_cloud().
5. Billing als Cloud-ADAPTER, nicht im Kern: Stripe/Webhook-Modul nur unter
   is_cloud() aktiv. Billing-Web-Feature (Scaffold) füllt den Org-Settings-
   Billing-Slot aus Track C (Entitlement-/Quota-Anzeige, Upgrade-CTA); On-Prem
   ausgeblendet.
6. On-Prem-Bootstrap im Lifespan: kein User + WHO2BE_BOOTSTRAP_ADMIN_EMAIL →
   Admin + Personal-Org + Workspace seeden.

GUARDRAILS (§3.6): Zugriff an Entitlement, NIE am Zahlungsstatus; Webhooks IMMER
signatur-verifizieren; KEIN Online-Call für On-Prem-Lizenz; NIE Private-Key im
Repo (nur K_pub); KEINE Billing-Logik im Kern; .env gitignored, keine Secrets im
Code. Security-sensible Stellen (Webhook, Krypto, Token) mit security-reviewer prüfen.

DATEIEN: neues licensing/-Modul (+ adapters/ + keys/ mit K_pub-Slot); core/config.py;
core/rate_limit.py (nur ergänzen); neue Migrationen (org_entitlement, mcp_usage);
neuer billing-Webhook-Router; agent-facing Read-Router (nur Gate-Dependency anhängen);
apps/web/src/features/billing/** (neu); main.py-Lifespan.
NICHT anfassen: Entity-Create-Pfade (KEINE Zähl-Limits); Tenancy-Mgmt-Routen
(Track C). RLS-Härtung (§3.6/§5) ist ein separater späterer Schritt — hier den
App-SQL NICHT umbauen.
```

### Track G — Dashboard-Viz + Pagination (Welle 2)
```
Branch: feat/dashboard-visualization-pagination
Ziel: Mehr Visualisierung, weniger nackte Zahlen; Activity nach ganz unten;
seitenbasierte Pagination der Activity.

Implementiere:
1. Status-Verteilung als Donut/Bar (CSS/SVG, KEINE neue Chart-Dependency).
2. KPIs visueller (z.B. Karten mit Mini-Visual statt purer Zahl).
3. Activity-Feed nach ganz unten; seitenbasierte Pagination (20/Seite) über
   status_history (Offset/Cursor im dashboard-Service).
4. Layout-Reihenfolge: Visuals oben, Activity unten.

DATEIEN: dashboard.py (Model), routers/dashboard.py, DashboardService,
apps/web/src/features/dashboard/**.
NICHT anfassen: alles andere.
```

### Track H — Agenten: Delete-UI, leere Hülle, Copy-Sperre (Welle 2)
```
Branch: feat/agents-shell-copy-delete
Ziel: Agenten löschbar (UI); leere Hülle ohne Persona/Template anlegbar; Copy,
aber gesperrt solange Hülle unvollständig.

Implementiere:
1. agent.py: persona_id + system_prompt_template_id in AgentCreate OPTIONAL
   (leere Hülle erlaubt). Status/Render toleriert fehlende Refs (unresolved).
2. POST /agents/{id}/copy — dupliziert Agent unter neuem Namen. 409/422 wenn
   Quell-Agent unvollständige Hülle ist (persona_id ODER template_id fehlt).
3. Web agents-Feature: Delete-Button (DELETE /agents/{id} existiert bereits),
   "Neuer leerer Agent"-Aktion, Copy-Aktion ausgegraut für unvollständige Hüllen.

DATEIEN: packages/models/agent.py, routers/agents.py + AgentService,
apps/web/src/features/agents/**.
NICHT anfassen: persona/system_prompt-Entitäten, MCP-Server.
```

### Track E — Resource-Composition + MCP-Stub (Welle 3, nach B+D)
```
Branch: feat/resource-composition-mcp-stub
Ziel: Sub-Resources (Resource→Resource, unendliche Tiefe, azyklisch); fetch_resource
liefert eigenen Body + Sub-Ref-Tabelle ohne Kinder-Expansion.

Implementiere:
1. Sub-Resource-Link analog playbook_resource_link (link_scope resource/block),
   neue Migration; azyklischer Recursive-CTE-Check vor Insert (wie
   playbook_composition).
2. resource.py-Model: sub_resources-Refs + ResourceRead-Erweiterung.
3. fetch_resource(id): eigener Body inline + Feld sub_resources:
   [{id, name, link_scope, block_id?, fetch_call: "fetch_resource('<id>')"}].
   KEINE Expansion der Kinder.
4. Web resource-Editor: Sub-Resource-Picker (reuse Resource-Picker-Muster).

DATEIEN: resource.py, neue Migration, ResourceService/Repo, apps/mcp/server.py
(nur fetch_resource), apps/web/src/features/resources/**.
NICHT anfassen: persona-Pills (Track F), Versionierung (Track A).

WICHTIG: auf gemergten Stand von B (+D) rebasen.
```

### Track F — Persona-Pills + Skills-Tabelle (Welle 3, nach B+D)
```
Branch: feat/persona-pills-skills-table
Ziel: Persona bekommt vollen Pill-Satz wie der System-Prompt + Skills als Tabelle,
damit Agenten überwiegend über die Persona (fetch-time-dynamisch) konfiguriert werden.

Implementiere:
1. Persona-BlockNote-Body: Slash-Refs (playbook/resource) + Katalog-Pills
   playbooks-catalog (all|triggered) + resources-catalog (all|tag) — Pill-
   Maschinerie aus dem System-Prompt wiederverwenden (nach Track B nur BlockNote).
2. Skills-Tabelle aus PersonaVersionContent.skills (SkillRef{name,note}) in der
   Persona-Detail-Page + im Katalog-Output.
3. get_persona: Katalog-Pills fetch-time gegen aktive Playbooks/Resources des
   Workspace rendern.

DATEIEN: persona.py (nur Pill/Skills-Render-bezogen), apps/mcp/server.py (nur
get_persona), apps/web/src/features/personas/** (Editor + Detail).
NICHT anfassen: Versionierung (A), Resource-Composition (E), body_format (B-Domäne).

WICHTIG: auf gemergten Stand von B (+D) rebasen.
```

---

## 5. Out of Scope / offen
- Konkretes Cloud-Pricing & Plan-Tiers (separater Plan, sobald MCP-Quota-Zahlen feststehen).
- **Postgres-RLS-Härtung (Cloud-Defense-in-Depth, §3.6):** eigener Hardening-Track —
  RLS-Policies + `SET app.current_tenant`-Kontext pro Request; On-Prem deaktiviert,
  ohne App-SQL zu ändern. Heute genügt app-seitiges `WHERE workspace_id` (ADR-0019).
- Konkrete Stripe/Mollie-Produktdefinition (`license_policy`/`short_code`) + Live-Secrets.
- FSL-LICENSE.md / CLA / Public-Switch (eigene bestehende Pläne `…1935_license-fsl-setup`, `…2028_public-switch-github-repo`).
- Enterprise-Hard-Hooks (SSO/SCIM/Audit-Export) — `…0528_enterprise-license-management` Phase B–D, trigger-basiert.
- Vektorisierung der Playbook-/Resource-Auswahl (bleibt tag/trigger-basiert).

## 6. Notes / Änderungen
**2026-06-02** — V1.1: Track D + §3.5 an die Notion-Vault-Standards *Deployment-
Standards (Single Codebase)* + *Licensing-Standards (Entitlements)* angeglichen.
Neu: Entitlement als Org-SSoT (App entscheidet, Provider meldet nur), hexagonaler
`EntitlementPort` mit Cloud-Webhook- + On-Prem-`K_pub`-Adapter, Billing als Cloud-
Adapter (nicht im Kern), Webhook-Signaturpflicht, Anti-Pattern-Guardrails (§3.6),
RLS-Härtung als eigener späterer Schritt (§5).
**2026-06-02** — V1.0: Initial-Anlage nach Brainstorming (12 Forks, 8 Tracks/3 Wellen).
