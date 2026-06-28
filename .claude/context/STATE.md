# STATE — Wo stehen wir (Snapshot, pro Run überschrieben)

_Stand: 2026-06-16_

## Funktioniert

- **System-/MCP-Feedback (zielloser Typ) (2026-06-28), Branch
  `feat/feedback-system-type` (gestapelt auf `feat/feedback-delete`):** Neuer
  Feedback-Typ fuer Probleme an der Plattform selbst (technisch/MCP), ohne
  Inhalts-Bezug. Modell: `entity_type='system'`, `entity_id=NULL`, Kategorie
  (technical/mcp/performance/other) im `signal`-Feld; fliesst in denselben
  Posteingang (Triage/Delete). Models: `SystemFeedbackCategory`,
  `SystemFeedbackCreate`, `FeedbackEntityType`; Read-Modelle
  (AgentFeedbackRead/FeedbackItem) auf `entity_id: UUID|None` +
  `signal: FeedbackSignal|SystemFeedbackCategory` geweitet. Migration 0059
  (`entity_id` NOT NULL gedroppt). Backend: `POST /system-feedback`
  (feedback_write-No-Op fuer Mensch, jede Rolle), Service/Repo
  `submit_system_feedback`/`insert_system_feedback`; `list_items` nimmt
  System-Zeilen mit Label „System" auf. MCP-Tool `report_problem` (Agenten
  melden MCP-/Tech-Fehler) + Client-Methode. Web: `ReportProblemDialog`
  („Problem melden" im Posteingang, Kategorie+Beschreibung), `submitSystemFeedback`
  im Client, Posteingang rendert System-Eintraege (Kategorie-Badge statt
  Signal, kein Detail-Link, Typ-Filter „System"); i18n de/en. **DoD gruen:**
  Python 900 pytest (System-Feedback-Inbox/Triage/Delete-Test + MCP
  report_problem-Test; OpenAPI-Golden regeneriert), mypy 300, ruff clean; Web
  412 Vitest (ReportProblemDialog + Inbox-System-Render), 0 Lint-Errors,
  tsc/build clean.

- **Feedback-Hard-Delete (Admin/Editor) (2026-06-28), Branch
  `feat/feedback-delete`:** Admin/Editor koennen einzelne Feedback-Eintraege
  loeschen. Backend: `DELETE /v1/workspaces/{ws}/feedback/{feedback_id}`
  (editor+-Gate via `require_role`, 404 bei fremdem Workspace, 204 bei Erfolg);
  Service `delete_feedback` + Repo `delete_feedback` (`DELETE FROM agent_feedback`
  mit workspace_id-Klausel als Verteidigung neben RLS). Migration 0058 grantet
  `DELETE ON agent_feedback` an `who2be_app` (war seit 0053 append-only nur
  SELECT/INSERT); die `feedback_resolution`-Triage raeumt der FK ON DELETE
  CASCADE (0054). **Kein** MCP-Tool (Kuration, nicht agent-facing). Web: geteilte
  `DeleteFeedbackButton` (Confirm-Dialog) im Posteingang (`FeedbackInbox`) **und**
  im Inline-`FeedbackPanel` neben der Triage; `deleteFeedback` in `client.ts` +
  beiden Feedback-Hooks (Reload nach Delete). i18n de/en. **DoD gruen:** Python
  898 pytest (Feedback-Test um Delete 204/404 + Cascade-Pruefung erweitert;
  OpenAPI-Golden regeneriert), mypy 300, ruff clean; Web 409 Vitest (neu:
  Inbox-Delete-Confirm), 0 Lint-Errors, tsc/build clean.

- **Fix: Builder-Playbook-Lock im Read-Pfad sichtbar (2026-06-27), Branch
  `fix/builder-playbook-is-managed-read`:** Das Playbook-Repository hat eigene
  `_select_current`/`_select_active` (Sonderspalten type/tags/triggers/
  is_composite) statt des generischen `versioned_repository`-SELECTs — und die
  ließen `p.is_managed` aus. Folge: `PlaybookRead.is_managed` war im GET/List
  immer `false`, die UI-Sperre (PR #282) griff für Builder-Playbooks nie und
  sie wirkten editierbar (Speichern lief serverseitig zwar in 403, aber der
  Lock war unsichtbar). Fix: `p.is_managed` in beide Playbook-SELECTs. Persona/
  Resource waren nie betroffen (nutzen `versioned_repository` mit `e.is_managed`).
  **DoD grün:** Python 898 pytest (Lock-Test um Playbook-GET `is_managed=true`
  + Update→403 erweitert; reproduzierte vorher den Bug), mypy 300, ruff clean.

- **Builder-Managed-Lock Web-UI (4/4, 2026-06-27), Branch
  `feat/builder-managed-ui`:** Macht den serverseitigen Lock (PR1–3) im
  Frontend sichtbar. `is_managed?` in den 5 Read-Typen (Agent/Persona/Playbook/
  Resource/SystemPromptTemplate). Neue geteilte `ManagedNotice` (Alert,
  „Vom System verwaltet" + optional Duplizieren-Hinweis, common-i18n de/en).
  Jede Detail-Page rendert bei `is_managed`: Notice oben, Editor read-only
  (Editor-Forms nehmen `locked` → verhalten sich wie Viewer; auch die bisher
  ungesperrten Name/Description/Type-Felder jetzt disabled, damit der Auto-Save
  keine vergeblichen 403-PATCHes feuert), keine Status-/Transition-Buttons,
  kein Lösch-/Danger-Zone, Persona-Playbook-Verknüpfen gesperrt. Agent-Page
  behält Duplizieren prominent (+ Hinweis), blendet nur Löschen aus.
  **DoD grün (Web):** lint 0 Errors, tsc clean, 408 Vitest (neu:
  ManagedNotice-Unit, AgentEditorForm-locked, PersonaDetailPage-managed),
  build clean. Damit ist die Builder-Lock-/Verteilungs-Reihe (4 PRs)
  vollständig. Kein Python berührt.

- **Builder-Content-Start-Sync (3/4, 2026-06-27), Branch
  `feat/builder-content-sync`:** Zentrale Verteilung von Builder-Updates an alle
  Workspaces ohne Per-Change-Migration. Neue Funktion
  `sync_managed_builder_content(conn)` (workspace_repository): hebt jede managed
  Builder-Persona/-Template/-4-Playbooks mit `managed_content_version <
  BUILDER_CONTENT_VERSION` workspace-übergreifend auf den kanonischen
  Sidecar-Stand (In-place-Replace des aktiven Versions-Inhalts) + stempelt neu.
  Verdrahtet in den FastAPI-Lifespan nach dem Bootstrap über eine
  **privilegierte Owner-Connection** (`settings.database_url`, da der App-Pool
  in Cloud RLS-scoped ist), fail-open (try/except, blockiert den Start nie).
  Künftige Updates = Sidecar-JSON editieren + `BUILDER_CONTENT_VERSION` erhöhen,
  keine Migration. Weil der Inhalt managed/gesperrt ist (PR1), gibt es keine
  User-Customizations zu überschreiben → sicheres Replace. **DoD grün:** Python
  898 pytest (neuer Sync-Test: veralteter Builder → 6 Aggregate restauriert,
  Stempel=1, idempotent zweiter Lauf=0, Feedback-Bullets wiederhergestellt),
  mypy 300, ruff clean. Folgt: PR4 Web-UI (Lock/Duplizieren sichtbar machen).

- **Builder Deep-Copy-Duplizieren (2/4, 2026-06-27), Branch
  `feat/builder-deep-copy`:** `copy_agent` macht für `is_managed`-Quellen jetzt
  einen Voll-Klon — neue Methode `AgentRepository.deep_copy` (eine Transaktion):
  Persona + die verknüpften Playbooks + Template werden als unverwaltete
  v1-active-Aggregate dupliziert (Inhalt der aktiven Quell-Version), der neue
  Agent zeigt darauf. Eindeutiger Klon-Slug fürs Template (UNIQUE-Constraint).
  Nicht-managed Quellen: unveränderte Shallow-Copy. **DoD grün:** Python 897
  pytest (Lock-Test erweitert: Klon → neue unmanaged Persona/Template + 4
  geklonte Playbooks, Persona editierbar), mypy 299, ruff clean. Folgt: PR3
  Start-Sync, PR4 UI.

- **Builder-Managed-Lock — Fundament (1/4, 2026-06-27), Branch
  `feat/builder-managed-lock`:** Neue Spalten `is_managed` + `managed_content_version`
  auf persona/playbook/resource/system_prompt_template/agent (Migration 0057,
  Builder per name/slug/Link gebackfillt + auf Content-Version 1 gestempelt; Seed
  setzt sie für neue Builder, Konstante `BUILDER_CONTENT_VERSION`). Edit-Lock
  `require_unmanaged` (403 `managed_aggregate`) an allen Mutations-Chokepoints
  (update/update_draft/restore/delete + version_status-Transition für alle 4
  Typen); `copy_agent` bleibt erlaubt → unverwaltete Kopie. `is_managed` in den
  Read-Modellen + SELECTs exponiert. **DoD grün (fresh DB):** Python 897 pytest
  (neuer Lock-Test: Builder update/transition/delete → 403, copy → 201 unmanaged),
  mypy 299, ruff clean. Folgt: PR2 Deep-Copy-Duplizieren, PR3 Start-Sync, PR4 UI.

- **Builder-Playbooks + Feedback (ADR-0038, Option C, 2026-06-27), Branch
  `feat/builder-playbook-feedback`:** Die vier Builder-Playbooks (persona/playbook/
  agent/consistency) bekommen eine kleine „Feedback"-Sektion (Heading+Paragraph):
  beim Lesen bestehender Elemente Veraltetes/Falsches via submit_feedback melden,
  Nutzung via record_usage. Quelle (4 *_body.json, +14 je) + Refresh-Migration
  0056 für Bestand (append an content.body, neue aktive Version, current_version
  gehoben; nur Playbooks, die an Persona 'Builder' geknüpft sind + Builder-Name,
  idempotent per Block-id). **DoD grün:** Python 896 pytest (Migrations-Test über
  alle 4 Playbooks), mypy 298, ruff clean. Web/API-Surface unberührt.

- **Builder-Feedback-Refresh-Migration (ADR-0038, 2026-06-27), Branch
  `feat/builder-feedback-refresh`:** PR #272 hat die Feedback-Bullets nur in die
  Seed-Quelldateien geschrieben; bestehende Workspaces (Builder vor #272 geseedet,
  Seed ist skip-if-exists) bekamen sie nicht. Migration 0055 zieht sie nach:
  hängt den Bullet an den aktiven Persona-/agent-builder-Template-Inhalt an
  (append-only, Customizations bleiben) und schreibt eine NEUE aktive Version
  (alte → inactive, current_version gehoben), idempotent per Block-id. DO-Block-
  Loops (Persona: blocks-Array; Template: stringified body). **DoD grün:** Python
  895 pytest (neuer Migrations-Test: alte v1 → v2 active mit Bullet, append-only,
  idempotent), mypy 297, ruff clean. Web unberührt.

- **Feedback-Seite Management-Redesign (ADR-0038, 2026-06-27), Branch
  `feat/feedback-management`:** `/feedback` ist jetzt ein Management-Center statt
  Statistik-Seite. Neuer Endpunkt `GET …/feedback-items` (alle Feedbacks
  workspace-weit + Element-Name + Triage-Status + KPI-Zähler, editor-gated, ≤500).
  Web: `FeedbackInbox` mit KPI-Leiste (klickbare Status-Filter) + Filtern
  (Status/Signal/Typ, client-seitig) + Inline-Triage je Eintrag; darunter der
  bisherige „Überblick" (Aggregate + Stale). Default „Offen". **DoD grün:** Python
  894, mypy 296, ruff clean; Web 405, 0 Lint-Errors, tsc/build clean.
- **Feedback-Triage (ADR-0038-Folge, 2026-06-27), Branch `feat/feedback-triage`
  (gestapelt auf `feat/feedback-unused`):** Triage pro Feedback-Eintrag,
  append-only gelöst — Migration 0054 `feedback_resolution` (FK→agent_feedback
  ON DELETE CASCADE, RLS, nur SELECT/INSERT); aktueller Status = jüngstes Event.
  Zustände addressed/in_progress/dismissed. `POST …/feedback/{id}/resolution`
  (editor-gated); `…/events` gibt pro Feedback den aktuellen Status mit aus.
  Web: Status-Select je Eintrag im FeedbackPanel-Drill-down. **DoD grün:** Python
  894, mypy 296, ruff clean; Web 402, 0 Lint-Errors, tsc/build clean. Damit sind
  beide Feedback-Folgen (Stale + Triage) erledigt.
- **Stale/Ungenutzt-Sicht (ADR-0038-Folge, 2026-06-27), Branch
  `feat/feedback-unused`:** „Ungenutzt" = Element mit aktiver Version, aber 0
  Usage/Feedback. Backend additiv (keine Migration): `GET …/feedback-unused`
  (UNION über persona/playbook/resource mit active-Version + NOT-EXISTS-
  Doppelfilter), editor-gated. Web: 3. Dashboard-Kachel „Ungenutzt" + Stale-
  Sektion auf der Feedback-Übersichtsseite. **DoD grün:** Python 894, mypy 296,
  ruff clean; Web 401, 0 Lint-Errors, tsc/build clean. (Triage folgt als
  nächster PR.)
- **Feedback-Nutzung im Agenten verankert (ADR-0038, 2026-06-27), Branch
  `feat/feedback-usage-anchoring`:** Damit Agenten das Flywheel auch *nutzen*
  (Tool verfügbar ≠ genutzt), dreifach instruktiv verankert: ① `tools-overview`-
  Resolver hängt bei aktivem `feedback_write` ein Rückmelde-Protokoll + Beispiel
  an (global, policy-gated); ② je ein Methodik-Bullet in den 5 Default-Templates;
  ③ Rückmelde-Disziplin in der Builder-Persona. Docs: agent-axes-Journey-Tabelle
  + ADR-0038. Backend-only, keine Migration. **DoD grün:** Python 894 passed
  (+3 Resolver-Tests), mypy clean, ruff clean.
- **Feedback-Views (ADR-0038-Surfacing, 2026-06-27), Branch
  `feat/feedback-views`:** Agenten-Feedback ist jetzt in der Web-UI sichtbar.
  Backend additiv (keine Migration): `GET …/feedback/{type}/{id}/events`
  (Drill-down, ≤50) + `GET …/feedback-overview` (workspace-weit, FULL-OUTER-JOIN
  beider Telemetrie-Tabellen), beide editor-gated. Web: `FeedbackPanel` auf den
  Detailseiten (Persona/Playbook/Resource) mit Verteilungs-Balken, Notizen,
  Lazy-Drill-down + „Überarbeiten"-Aktion; `FeedbackTiles` aufs Dashboard;
  eigene Übersichtsseite `/w/{ws}/feedback` + Nav-Eintrag. **DoD grün:** Python
  891 passed, mypy 296, ruff clean; Web 400 Tests, 0 Lint-Errors, tsc/build clean.
  Offen (bewusst): Triage als append-only Resolution-Event.
- **Track 4-C Write-Rate-Limit (ADR-0039 abgeschlossen, 2026-06-27), Branch
  `claude/track4-finer-rights`:** `AgentToolPolicy.write_rate_limit: int|None`
  (Writes/Min; None=unbegrenzt, JSONB-abwärtskompatibel) + `is_within`-Anti-
  Escalation; Gate `require_write_rate` (Sliding-Window `token_rate_limiter`,
  Key `write:{agent_id}`, 429) nach `require_capability` in allen Write-Pfaden
  von persona/playbook/resource; `whoami` gibt das Limit aus; AgentEditorForm hat
  ein optionales Zahlenfeld. Damit ist ADR-0039 (alle 3 Achsen + Rate-Limit)
  vollständig. **DoD grün:** Python 891 passed, mypy 296, ruff clean; Web 393
  Tests, 0 Lint-Errors, tsc/build clean.
- **Track 4-B Tag-Scoping (ADR-0039, 2026-06-27), Branch
  `claude/track4-finer-rights`:** `AgentToolPolicy.write_tags` (Dict Domain→Tags;
  leer=unrestricted) + `require_write_tags`-Gate in persona/playbook/resource
  create+update+restore (eingehende Tags immer, Bestands-Tags beim Update →
  keine Übernahme out-of-scope). `is_within`-Anti-Escalation. DB-Integrationstest
  grün; volle Suite 888 passed, mypy 296, ruff/Web clean. Offen: UI-Widgets für
  write_tags/transition_grants/Ablauf + Rate-Limit.
- **Track 4-B write_tags-UI + whoami (2026-06-27):** AgentEditorForm hat den
  Tag-Picker (3 Domain-Felder → write_tags-Dict); whoami gibt write_tags +
  transition_grants aus. Web 392 Tests grün, Python 888, mypy 296, ruff clean.
  ADR-0039 komplett: transition_grants-Toggles + Token-Ablauf-Feld im
  Editor/Token-Sektion. Alle 3 Achsen mit Backend+UI. Python 888, mypy 296,
  ruff clean, Web 393/0-Lint/build. Offen nur optionales Write-Rate-Limit.
- **Track 4-B Web-Policy-Editor-Sync (2026-06-27), Branch
  `claude/track4-finer-rights`:** Der `AgentEditorForm` exponiert jetzt die
  feineren Backend-Capabilities `system_prompt_write` (ADR-0040, aus) +
  `feedback_write` (ADR-0038, secure-by-default an) als Write-Switches
  (types.ts/DEFAULT_TOOL_POLICY, useAgentForm-Schema, i18n de/en, Test). Web-DoD
  grün (tsc/lint/391 Tests/build). Offen aus Track 4-B: Tag-Prädikat-Write-
  Scoping (Backend) + UI für transition_grants/Token-Ablauf.
- **Track 4-A feinere Rechte (ADR-0039, 2026-06-27), Branch
  `claude/track4-finer-rights` (gestapelt):** getrennte Promote/Retire pro Domain
  (`transition_grants`, Narrowing von `promote_retire`) + Token-TTL
  (`TokenCreate.expires_at`; Enforcement+Spalte gab es schon). Additiv, DB-frei
  verifiziert. Track 4-B (Tag-Scoping + Web-Policy-Editor) offen.
- **Track 2 Search (ADR-0037, 2026-06-27), Branch `claude/track2-search`
  (gestapelt):** MCP-Tool `search` + `GET /search` — Postgres-Runtime-Volltext
  über Name + Content der aktiven Version, read-scope-gefiltert, nur active.
  Kein Migration (GIN-Index + pgvector als Folge). ruff/mypy clean; eigener PR.
- **Track 3 Feedback-Flywheel (ADR-0038, 2026-06-27), Branch
  `claude/track3-feedback-flywheel` (gestapelt):** append-only `usage_event` +
  `agent_feedback` (Migration 0053, RLS + SELECT/INSERT-only), Capability
  `feedback_write` (default an), Repo/Service/Router + MCP-Tools `record_usage`/
  `submit_feedback`/`get_feedback`. Telemetrie fliesst nie in einen Prompt (kein
  Injection-Vektor). ruff/mypy clean, DB-freie Tests grün; eigener PR.
- **Builder-System-Prompt-Tools (ADR-0040, 2026-06-27), Branch
  `claude/charming-pasteur-pxz2l8`, PR #266:** Der Builder kann System-Prompt-
  Templates über MCP verfassen/anpassen/lesen + draft→review einreichen; das
  Aktivieren (→active) bleibt für Agent-Token hart gesperrt (Injection-Schutz).
  Neue Capability `system_prompt_write` (secure-by-default; Builder-Seed +
  Migration 0052). Neue MCP-Tools `list/get/create/update/restore/transition_
  system_prompt`; Track-1-Versions-Tools decken `entity_type='system_prompt'`
  mit ab. security-reviewer clean. Web-UI-Policy-Toggle → Track 4.
- **AI-native MCP-Ausbau (2026-06-27), Branch `claude/charming-pasteur-pxz2l8`,
  PR #266:** Design für 4 Tracks abgelegt (Plan
  `.claude/plan/2026-06-27-1100_ai-native-mcp-and-rights.md`; ADR-0037 Search,
  ADR-0038 Feedback-Flywheel, ADR-0039 feinkörnige Write-Rechte). **Track 1
  implementiert:** neue MCP-Read-Tools `find_usages`/`list_versions`/
  `get_version`/`diff_versions` (dünne Adapter über bestehende REST-Endpunkte,
  Entity-Dispatch). 12 Tool-Tests + MCP-Suite (111) grün, ruff/mypy sauber.
  Tracks 2/3/4 offen.
- Phase 1–3 abgeschlossen: Tenancy, Status-Workflow + Dashboard, Resources +
  BlockNote, Multi-User-RBAC, MCP Read/Write-Tools, Einzel-Delete/Export, i18n.
- Security-Findings (Phase 1 + 2) alle **Closed**, Ampel Grün.
- MCP-HTTP-Transport (ADR-0034) + Per-Request-Bearer + Ein-Klick-MCP-Config;
  Agent-Read-Scope secure-by-default; API-Tokens am Agenten verwaltet.
- **Per-Agent-Connector-URL (ADR-0036-Addendum, 2026-06-25), Branch
  `claude/determined-noether-wi53zd`:** `…/mcp?agent=<uuid>` macht die Connector-URL
  pro Agent eindeutig (Claude-Dedup); `authorize` akzeptiert kanonische Resource oder
  Basis+`?agent=`, Consent sperrt den signierten Agenten hart (client-Wert ignoriert),
  Membership-Prüfung bleibt autoritativ. UI: `AgentConnectorSection` (kopierbare URL,
  kein Token). Security-Review clean; Python/Web-DoD lokal grün; E2E gegen echten
  Claude-Client offen (Fail-safe: ohne Query gilt Consent-Auswahl).
- **OAuth-Remote-MCP-Connector (ADR-0036), Branch `feat/oauth-remote-mcp`:**
  Who2Be ist OAuth-2.1-AS (`apps/api` `/oauth/*` + Metadaten), MCP ist RS
  (FastMCP `RemoteAuthProvider`, PRM/401), Consent-UI (`apps/web`
  `/oauth/consent`). DCR + PKCE + agent-gebundener `w2b_`-Access-Token +
  rotierende Refresh-Tokens. Security-Review durch, Befunde behoben (RLS-Bruch
  in Cloud, Consent-Phishing, Rate-Limits, Refresh-Re-Auth, konstantzeit-PKCE).
- Public-Switch-Vorbereitung: LICENSE.md (FSL-1.1), CONTRIBUTING.md, SECURITY.md;
  Notion-Entkopplung; LLM-Standards-Schicht (`docs/standards/`, `AGENTS.md`,
  `.claude/context/`).
- Lokale Verifikation grün: ruff, mypy strict, Web (lint/tsc/387 Tests/build),
  **gesamte pytest-Suite grün (765 passed, 0 failed)** gegen eine Wegwerf-Postgres.
- **Deploy verdrahtet:** `deploy/hetzner` (api + mcp-http) trägt die OAuth-Env
  (aus `DOMAIN` abgeleitet); README/`.env.example` aktualisiert. Feature greift
  damit im echten Cloud/On-Prem-Deploy (Caddy `api./app./mcp.` + `--profile mcp-http`).
- **OAuth-Smoke beide Editionen grün** (`scripts/oauth_smoke.sh onprem|cloud`,
  Doku `docs/oauth-smoke.md`): voller Flow gegen echten API+MCP-Prozess, Cloud
  als `who2be_app` (RLS aktiv). Fand + fixte einen Cloud-Bug: fehlende
  `who2be_app`-GRANTs auf den OAuth-Tabellen (Migration 0049 ergänzt).

## In Arbeit

- OAuth-Connector: **E2E mit echtem Claude/ChatGPT-Client** steht aus (braucht
  Stack mit `api.`/`app.`/`mcp.`-Subdomains). Offen-Tasks: TTL-Cleanup der
  OAuth-Tabellen, optional Audience-Trennung am RS, MFA/aal2-Consent (Phase 2).

## Bekannte Probleme

- **CI-Runner-Infra defekt:** alle GitHub-Actions-Jobs scheitern in ~2 s,
  `runner_id=0`, keine Logs → mutmaßlich erschöpfte **Actions-Minuten / Billing**
  des privaten Repos. Nicht im Code behebbar. **Public-Flip löst es** (Actions ist
  für öffentliche Repos frei/unbegrenzt).
- E2E-Gate bleibt Soft, bis die CI-Infra steht.

## Nächste Schritte (nicht-Code, manuell beim Owner)

1. CI-Billing klären **oder** direkt auf Public flippen.
2. GitHub-Settings: Description, Topics, Issues/Discussions/Security-Advisories,
   Branch-Protection (CI-grün-Required erst nach CI-Fix).
3. CLA-Assistant aktivieren.
4. Visibility Private → Public (finaler Flip durch den Owner).
