# STATE — Wo stehen wir (Snapshot, pro Run überschrieben)

_Stand: 2026-07-18_

## Funktioniert

- **Builder-Content v8: Agent-Memory-Wissen UMGESETZT (2026-07-19, Branch
  `claude/autonomous-code-agent-setup-iz6ydx` neu ab main, PR #325):**
  Folge-PR zu #324 — Agent-Playbook („tool_policy verstehen": memory_mode/
  memory_directive, Empfehlungslogik suggest+recommended, is_within-Grenze
  mit Human-Hand-Off) + neue Gedaechtnis-Sektion in den Agent-Bau-
  Konventionen; `BUILDER_CONTENT_VERSION` 7→8 (Start-Sync, keine Migration).
  DoD gruen: ruff/format/mypy clean, 1085 pytest passed, Coverage 90,48 %.

- **Agent-Memory (ADR-0044) UMGESETZT (2026-07-18, Branch
  `claude/autonomous-code-agent-setup-iz6ydx`, PR #324):** Kuratiertes
  Langzeitgedächtnis pro Agent, in drei Design-Runden mit dem User
  entschieden. Kern: 4-stufiger `AgentToolPolicy.memory_mode`
  (off<read_only<suggest<auto, Default off, `is_within`-geordnet) +
  `memory_directive` (muss/soll); Freigabe-Schleuse `pending`→Triage→
  `active`/`rejected` (rejected bleibt Dedup-Basis); kein agent-seitiges
  Update/Delete (human-only Management, Agent-Tokens hart ausgeschlossen).
  Migration 0066 `agent_memory` (tsvector `simple`+GIN, pg_trgm mit
  dynamisch qualifizierter Opklasse — Supabase-/Schema-robust, RLS+Grants).
  3 MCP-Tools `search_memory`/`list_memories`/`save_memory` (Kap.-10.5-
  Kriterien in Beschreibungen; **57 Tools im ADR-0042-Mapping**, neue
  `memory`-Achse in `ToolRequirement`). **Laufzeit-Einbindung (WP-6):**
  `get_persona`/`PersonaService.render` hängt fetch-time die Gedächtnis-
  Sektion an `body_rendered` (Anweisung + Top-5 freigegebene Memories,
  Daten-Rahmung) — der konfigurierte System-Prompt wird nicht live
  aktualisiert, die Persona schon. Wächter serverseitig (Injection-Regex,
  Importance≥5, Trigram-Dedup, Cap 500, Write-Rate-Limit); Nutzungs-Log
  `retrieval_count`/`last_retrieved_at` (selbstlimitierend 1 Write/Min).
  Security-Review: 0 kritisch/mittel, N-1/N-2 gefixt, N-3 dokumentiert.
  Web: Gedächtnis-Sektion Agent-Detail (Triage mit `context`-Anzeige,
  Nutzungs-Log, Einzel-/Alles-Löschen, rejected eingeklappt) +
  memory-Selects im Policy-Editor. DSGVO: Export `agent_memories` +
  FK-CASCADE-Löschung + VVT V17. **DoD grün (lokal, Postgres 16):** ruff/
  mypy strict clean, **1085 pytest passed, Coverage 90,48 %** (Gate 85);
  Web lint 0 Errors, tsc clean, **902 Vitest, Branches 80,99 %** (Floor 79),
  build clean. Plan: `.claude/plan/2026-07-18-1500_agent-memory.md`.
  ADR: `docs/adr/0044-agent-memory.md`.

- **Externe Tools (WP-1–5) UMGESETZT (2026-07-18, Branch
  `claude/autonomous-code-agent-persona-iikbwe`, PR #316):** Versionierte
  Workspace-Aggregate `external_tool` (WP-1) mit Alias-Eindeutigkeit pro
  Workspace, Migration 0065, Status-Workflow draft→active→inactive,
  GDPR-Export (Kaskaden-FK). Placeholder-Art `tool-ref` mit Resolver +
  Katalog-Eintrag (WP-2): Pills referenzieren Alias, Fetch-Time-Expansion
  zur aktiven Bindung (display_name, tool_names, usage_notes, fallback_note).
  6 MCP-Tools: `list/get_external_tool` (Read-Scope-gefiltert) +
  `create/update/transition/restore_external_tool` (capability
  `external_tool_write`, Default aus; WP-3) — **54 Total im Mapping**
  (`who2be_models.tool_requirements`, Drift-Guards gruen). Web-Features
  (Liste+Detail nach Resources-Muster, BlockNote fuer usage_notes; WP-4).
  ToolPicker + tool-ref-Pill in System-Prompt-, Playbook-, Persona-Editor;
  Resource-Editor rendiert bewusst keine Pills (kein `render_template_body`-
  Pfad, bauartbedingt; WP-5). Keine Feedback-Migration (entity_type in
  Pydantic, nicht DB-CHECK). **DoD gruen:** ruff/mypy/pytest (Coverage
  89,43 %), **1120 passed** (unverändert), lokal verifiziert; Web lint/tsc/
  Vitest **893 Tests, Branches 81,14 %** (Floor 79), build clean.
  Plan: `.claude/plan/2026-07-18-1315_external-tools-tool-ref.md`. ADR:
  `docs/adr/0043-external-tool-bindings.md`.

- **Playbooks-UI/UX-Redesign UMGESETZT (2026-07-11, Branch
  `claude/code-agent-setup-1pes6m`):** Design-Handoff
  „Playbooks_UIUX_Verbesserung" (Screens 2a/2d/3a/3b) in `apps/web`
  nachgebaut. **Übersicht:** Karten-Zeilen statt `DataList` (neue
  `PlaybookRow` mit Typ-Icon-Chip aus Pill-Tokens via `lib/typeMeta`,
  Soft-Status Dot+„Aktiv · v2", „Entwurf offen"-Brand-Pill, `Zap`+Trigger-
  Chips max 3+„+N", aufklappbarer Composite-Footer mit verlinkten Kindern,
  „Teil von"-Marker clientseitig aus der compose_children-Rückrichtung);
  Filterleiste = Segmented-Status + Suche (Name ODER Trigger — neuer
  optionaler `searchText`-Accessor in `useListFilters`) + „Filter"-Popover
  (Tag/Typ/Agent/Gruppieren); Onboarding-Hero + gefilterter Leerzustand;
  Header mit Count-Pill (`PageHeader.titleAddon` neu). **Detail:** Tabs
  Bearbeiten/Beziehungen/Versionen (`PlaybookDetailTabs`, ARIA-Tabs mit
  Pfeiltasten), Hero mit Typ-Icon + Status-Pill, `ReviewBanner` (ersetzt
  BranchStatus-Block; gleiche BranchActions + exportierter `SaveIndicator`),
  Beziehungen-Tab = Verwendet-in (Avatar-Initialen) + `SubPlaybookFlow`
  (nummerierter Ausführungs-Flow) + ComposedBy + Resource-Links +
  FeedbackPanel (Revise springt in Bearbeiten-Tab), Danger-Zone kollabiert;
  geteilte `VersionHistory` auf sanfte `StatusBadge`-Chips umgestellt
  (wirkt auf alle 4 Detail-Pages). Prototyp-Off-Scale-Werte bewusst auf die
  Token-Skala gerundet (Plan §Entscheidungen). **DoD grün:** lint 0 Errors,
  tsc clean, 790 Vitest passed, Branches 81,77 % (Floor 79), build clean.
  Plan: `.claude/plan/2026-07-11-1200_playbooks-uiux-redesign.md`.
- **Builder v7: Konventionen-Pointer-Fix UMGESETZT (2026-07-11, Branch
  `claude/builder-agent-role-eupbyq`, Pflege-Lauf 3):** Die fünf
  gleichlautenden incorrect-Signale („Agent-Bau-Konventionen wird
  mitgeliefert (link_scope resource)" — real ist der Link `lazy`,
  `linked_resources` kommt leer) sind behoben: Prosa in allen 5
  Builder-Playbook-Sidecars + der Resource-Selbstbeschreibung auf den
  realen lazy-Pointer korrigiert inkl. expliziter
  fetch_resource-Nachlade-Anweisung (resource_id aus `linked_blocks`, kein
  UUID-Hardcoding); Entscheidung lazy-statt-inline in DECISIONS.md
  (2026-07-11). Mitkorrigiert: `fetch_playbook`-Docstring +
  `PlaybookWithResources`-Doku (versprachen Volldokument für alle
  resource-Scope-Links), Seed-Kommentar; Agent-Playbook bietet im Hand-Off
  jetzt den Konsistenz- & Drift-Check an (Persona-Abgleich).
  `BUILDER_CONTENT_VERSION` 6→7 (Verteilung via Start-Sync). Triage:
  4 Alt-Signale (get_agent-Reads, fetch_agent-self-only, Modi-Regel,
  Trigger-Kollision) sind in den aktuellen Versionen bereits behoben —
  Schließung via resolve_feedback erst NACH Merge+Deploy dieses Fixes
  (managed-Regel). DoD: ruff/format/mypy clean, **1002 pytest passed
  (0 skipped) gegen lokale Postgres 16, Coverage 90,23 %** (Gate 85).

- **Feedback-Resolve für Agenten + Builder v6 UMGESETZT (2026-07-10, Branch
  `claude/builder-agent-setup-pyczxa`, Folge-PR zu #303):** Neue Capability
  `feedback_resolve` (User-Entscheidung; Default False, is_within-Escalation,
  Policy-UI-Toggle + i18n); `set_resolution` bekam das fehlende
  Capability-Gate für Agent-Tokens; `get_feedback` additiv um
  `recent_feedback` (id/signal/note/resolution=jüngstes Triage-Event)
  erweitert; neues MCP-Tool `resolve_feedback(feedback_id, resolution,
  note?)` (addressed/in_progress/dismissed, dismissed nur mit Note;
  tools-overview capability-gekoppelt). Builder-Content v6: Pflege-Lauf
  triagiert nur offene Signale und schließt nach Freigabe selbst
  (Report-Sektion D = Geschlossene Signale; Managed-Signale erst nach
  verteiltem Repo-Fix). Sync-Novum: Start-Sync zieht erstmals auch die
  tool_policy der Managed-Agenten nach (Builder/Builder-Lite,
  feedback_resolve=True). DoD: ruff/format/mypy strict clean, 971 pytest
  passed, Coverage 90,19 % (Gate 85); Web lint/tsc/build clean, 781 Vitest,
  Branches 81,47 %. Details: DECISIONS.md 2026-07-10 (Feedback-Resolve).
- **MCP tools/list pro Agent policy-gefiltert UMGESETZT (2026-07-10, Branch
  `claude/code-agent-setup-h3khxa`, PR #305, Issue #304, ADR-0042):** Neues
  SSoT-Modul `who2be_models.tool_requirements` (`MCP_TOOL_REQUIREMENTS` für
  alle 47 MCP-Tools; `is_tool_visible` policy-basiert für die API,
  `is_tool_visible_for` whoami-basiert für den MCP-Adapter). MCP:
  `PolicyFilterMiddleware` (FastMCP 3 `on_list_tools`/`on_call_tool`) filtert
  `tools/list` per Request nach der Token-Policy (whoami-Cache pro
  Token-SHA-256, LRU 512/TTL 300 s) und sperrt Calls ausgeblendeter Tools mit
  klarer Meldung; **fail-open** bei Auflösungsfehlern (kein „verbunden, aber
  keine Tools"-Rückfall; ping bleibt token-frei). API: `ToolsOverviewResolver`
  delegiert Sichtbarkeit an dieselbe SSoT (`_ToolDoc.tool_names`,
  `is_write`-Property statt Capability-Duplikat) — Prompt-Text und echte
  Tool-Liste können nicht mehr driften. Drift-Guards beidseitig als Tests
  (MCP-Registry == Mapping; API-Gruppen ↔ Mapping mit dokumentierter
  Ausnahmen-Liste). **Neue MCP-Tools brauchen einen Mapping-Eintrag** (sonst
  CI rot). Default-Policy-Agent sieht 21 statt 47 Tools (Payload-Ersparnis,
  Claude-Chat-Budget). KEINE Security-Grenze: API-Durchsetzung (ADR-0039)
  unverändert autoritativ. DoD: ruff/format/mypy strict clean (316 Dateien),
  **984 pytest passed (0 skipped) gegen Wegwerf-Postgres, Coverage 90,17 %**
  (Gate 85). Plan: `.claude/plan/2026-07-10-1524_mcp-per-agent-tool-filtering.md`.
- **Builder v5: Persona-Modi + Konventions-Resource UMGESETZT (2026-07-10,
  Branch `claude/builder-agent-setup-pyczxa` neu ab main, Folge-PR zu #302):**
  Builder-Persona ist jetzt Multi-Mode — Architekt (Default, Vier-Phasen-Bau),
  Kurator (Pflege-Haltung, Trigger identisch zum Playbook „Library-Pflege &
  Feedback-Lauf", report-first, Prosa-Bindung statt playbook_id) und Berater
  (Read-only-Auskunft, enge Phrasen-Trigger, ohne Phasen-Zeremonie); Basis-
  Identität entsprechend gescoped. Neue Managed-Resource
  „Agent-Bau-Konventionen" (8 Sektionen) als Single-Source, per
  link_scope='resource' aus allen 5 Builder-Playbooks verlinkt; duplizierte
  Konventions-Prosa in den Playbooks auf Pointer eingedampft. Seed/Sync:
  Resource-Insert-missing + Content-Update analog Playbooks,
  `BUILDER_CONTENT_VERSION` 4→5, keine Migration (Konvention). Deep-Copy
  kopiert Resource-Links NICHT (Baseline fixiert). DoD: ruff/format/mypy
  strict clean, 955 pytest passed, Coverage 89,94 % (Gate 85); Baselines
  (Dashboard active_resources, Resource-Tags, Seed-/Sync-/Lock-Tests)
  nachgezogen. Details: DECISIONS.md 2026-07-10 (Builder v5).
- **Builder-Rework: Library-Pflege-Routine + Beziehungs-Denken UMGESETZT
  (2026-07-10, Branch `claude/builder-agent-setup-pyczxa`, PR #302, Draft):**
  Fünftes Managed-Playbook „Library-Pflege & Feedback-Lauf" (Sidecar
  `builder_playbook_maintenance_body.json`, 6 Phasen: Sammeln → Triage →
  Zusammenhänge/Lücken → Freigabe → Drafts → Hand-Off; Managed-Funde →
  Repo-Hand-Off, Feedback-Schließung via UI gelistet, ADR-0038).
  Beziehungs-Denken im Persona-Profil (Graph-Prinzip, search/find_usages vor
  Neuanlage, set_*-Verdrahtung + fetch_*-Verifikation danach).
  Feedback-Backlog eingearbeitet (Modi-Regel im Persona-Playbook;
  fetch_agent-self-only-Ersatzindikatoren im Agent-Playbook; Konsistenz-Check:
  Scope-Abgrenzung „kein Code-/Repo-Audit", neue read-only
  Zusammenhangs-Checks, entschärfte Trigger — Kollision „pruefen"/
  „qualitaetscheck" behoben). `sync_managed_builder_content` erweitert:
  Insert-missing (neue Playbooks erreichen Bestands-Workspaces ohne
  Migration) + Metadaten-Nachzug (`type`/`tags`/`triggers` auf der
  Playbook-Row; Drift-Lücke geschlossen). `BUILDER_CONTENT_VERSION` 3→4.
  DoD: ruff/format/mypy strict clean, 953 pytest passed, Coverage 90,13 %
  (Gate 85), Seed-/Sync-/Lock-/Dashboard-/Tag-Tests nachgezogen; keine neue
  Migration (Entscheidung im Sync-Docstring + DECISIONS.md 2026-07-10).
- **Builder-Befähigung + Agent-Filter + UI-Polish UMGESETZT (2026-07-09,
  Branch `claude/builder-agents-ui-improvements-o454yy`, PR #301):** Alle 6
  WPs des Plans `2026-07-09-1556_builder-agents-ui-improvements.md` per
  sequenziellem Agenten-Workflow implementiert. **D1:** Trigger-Normalisierung
  (Validator `normalize_triggers` Split `,`/`;`+dedupe, `splitTriggers` auf
  `[,;]`, Aggregat-SQL `regexp_split_to_array`, Migration 0063 normalisiert
  Bestand in-place über ALLE Versions-Snapshots, idempotent). **B:**
  `?agent=<uuid>` auf den 3 Listen-Endpoints (neue
  `agent_filter_*_ids`-Funktionen in `agent_scope.py`, 404 bei fremdem Agent,
  Schnittmenge mit Policy-Restrict; Persona-Repo bekam restrict_ids) +
  Agent-Facette in `useListFilters`/`ListFilterBar` (serverseitig, Refetch)
  auf allen 3 Listen; `useAgents` → `@/hooks`. **D2/D3:**
  `PlaybookRead.compose_children` (Batch-Select, beide SELECT-Pfade, kein
  N+1; MCP liefert automatisch mit), Trigger-Einzel-Pills (max 3 + „+N"),
  Composite-Badge + verlinkte Sub-Playbooks, Group-by `?group=none|type|
  composite` (Anzeige-Präferenz, zählt nicht als Filter). **E:** neue
  `PersonaPlaybooksCard` — Anzeige-Modus (Links/StatusBadge/Composite/Typ+
  Trigger-Zahl) + Bearbeiten-Modus mit Suche hinter Button; `splitTriggers`
  → `@/lib/triggers` (Cross-Feature-Gate). **C:** Diff-Endpunkte liefern
  additiv `before_text`/`after_text` (neue Single-Source `blocks_plain_text`
  in `placeholders/_core.py`, Resolver-Duplikate darauf umgestellt);
  `VersionDiffView` rendert unified Git-Diff (eigene `lineDiff`-Utility,
  Fallback ohne before_text intakt). **F:** `PersonaService.render(mode=…)`
  (case-insensitiv, 422 mit Modi-Liste, `PersonaRenderResponse.mode`
  additiv), REST `?mode=`, MCP `get_persona(mode=…)`, persona-ref-Anweisung
  ergänzt. **A:** Docstring-Fix create/update_system_prompt (BlockNote-
  placeholder-Format statt toter Liquid-Syntax), neues Model
  `placeholder.py` + `GET …/placeholders`-Katalog aus der REGISTRY + MCP-Tool
  `list_placeholders`, 4 Builder-Seed-Playbooks aktualisiert (ADR-0040-
  Widerspruch aufgelöst: Templates via MCP verfassen erlaubt; Placeholder-
  Authoring; Modi-Kriterien; Token-Spar-/Wiederverwendungs-Strategie),
  `BUILDER_CONTENT_VERSION`++ (Start-Sync verteilt). **DoD je WP grün**
  (ruff/mypy strict/pytest ≥966–951 passed, Coverage ~89–90 %, gegen echte
  Wegwerf-Postgres; Web 736→765 Vitest, Branches 80,6→81,2 %, lint/tsc/build
  clean); CI auf dem Zwischenstand (D1+B+D2/D3) komplett grün.
- **Standards-Review UMGESETZT (2026-07-08, gleicher Branch/PR #299):** Die
  Audit-WPs 1–8 sind implementiert (2 Agenten-Wellen, 8 Commits). Highlights:
  Web-Coverage-Schuld abgetragen — Branches 69,52 % → **80,64 %** (Floor 79),
  734 Tests (davon ~280 neu, inkl. A11y für Auth/Detail/agents/system-prompts/
  legal; `api/client.ts` 100 % Branches) → entsperrt den roten `main`-web-Job
  samt maskierter A11y-/Build-/Bundle-Gates; DSGVO-Purge deckt jetzt
  `agent_feedback`/`usage_event`/`oauth_*` ab + `cleanup_expired_oauth()`
  (VVT/C5/Retention nachgezogen, 960 pytest grün); REST↔MCP-Paritätstest +
  `contract`-Marker (TST-4 geschlossen); DoD-Drift strukturell zu (CONTRIBUTING
  führt, `test:coverage`/`--cov-fail-under=85` lokal = CI); Test-Strategie-ADR
  0032→**0041** + Status-Flips 0037/0038/0040; ESLint-`FEATURES` dynamisch +
  personas→resources-Import aufgelöst; `resolve_org_id`-Helper +
  Export-Konsolidierung (`routers/_export.py`); `aal_missing_onprem`-Warn-Event
  + `WHO2BE_REQUIRE_MFA_ONPREM`. **Offen/Owner:** ADR-0002 enforce-vs-amend
  (COD-1/3), E2E-Journeys (TST-5) + Gate-Härtung, `coverage.all`-Entscheidung,
  WP-9 (CLA/AVV/Kontakt). Details: `docs/standards-review-2026-07-08.md` §3.
- **Standards-Review 2026-07-08, Branch `claude/code-agent-setup-1cdosv`:**
  Repo-weites Audit gegen alle sechs Standards aus `docs/standards/` (sechs
  parallele Prüf-Agenten, Security via `security-reviewer`; Tooling-Gates +
  CI-Run #644 real verifiziert). Ergebnis + Umsetzungs-Change-Log (WP-1–9):
  `docs/standards-review-2026-07-08.md`. Kernbefunde: Security 🟢 (TODO 1–3
  + F-12 verifiziert geschlossen, nur ADR-akzeptierte Rest-Risiken);
  Testing 🔴 (main-CI rot: Branch-Coverage 69,52 % < 79 % = exakt 241
  Branches, maskiert A11y/Build/Bundle-Gates; Root-Cause DoD-Drift
  `npm test` ohne Coverage; REST↔MCP-Paritätstest fehlt trotz „umgesetzt");
  Frontend 🟡 (ESLint-`FEATURES`-Liste veraltet → 7/11 Features ohne
  Cross-Feature-Gate, erster Verstoß personas→resources durchgerutscht);
  Compliance 🟡 (DSGVO-Purge deckt `agent_feedback`/`usage_event`/`oauth_*`
  nicht ab; VVT stale ggü. Schema 0062); Coding 🟡 (ADR-0002-Schichtregel
  real verletzt: HTTPException in 23 Services, SQL in ~10 Services + 2
  Routern); Methode 🟡 (CLAUDE.md „Aktueller Stand" ~4 Wochen alt,
  ADR-0032 doppelt vergeben, Plan-README ungepflegt, ADR-Status
  0037/0038/0040 fälschlich „Proposed"). Empfohlene Reihenfolge: WP-1
  Coverage-PR (entsperrt 4 Gates) → WP-2 DoD-Drift → WP-3 DSGVO-Purge.

- **Fix: MCP-tools/list-Payload −72 % — Claude Chat zeigt Tools wieder
  (2026-07-07), Branch `claude/who2be-mcp-tools-discovery-y4bxde`:** Zweites,
  vom OAuth-Lockout unabhängiges Problem hinter „verbunden, aber keine Tools":
  Live-Logs zeigten Auth 200 + `ListToolsRequest` 200, Claude Chat blieb
  trotzdem leer. Messung: die tools/list-Antwort war **230 KB** für 46 Tools —
  72 % davon die von FastMCP 3 auto-generierten `outputSchema`-Blöcke aus den
  Pydantic-Rückgabetypen. Claude Chat budgetiert die Connector-Tool-Payload
  hart und verwarf die Liste komplett (Claude Code verdaut sie, daher dort
  sichtbar). Fix: alle 46 Tool-Registrierungen mit `output_schema=None`
  (MCP-optional; Ergebnisse fließen unverändert als Text/structured content) →
  **65 KB**. Tests auf `structured_content`/Text-Content umgestellt (ohne
  Schema hydriert `result.data` nicht mehr; Listen ohne structured_content).
  DoD: 127 MCP-Tests, ruff, mypy grün; Tool-Call-Smoke lokal.
- **Fix: MCP-Tool-Discovery-Lockout (OAuth-Refresh-Reuse) (2026-07-05), Branch
  `claude/who2be-mcp-tools-discovery-y4bxde`:** Claude-Agenten verloren nach der
  OAuth-Umstellung dauerhaft alle Who2Be-MCP-Tools („verbunden, aber keine
  Tools"). Repro gegen echten Stack (Wegwerf-Postgres + API + MCP-HTTP): eine
  Runtime mit veralteter Refresh-Kopie (>30s-Grace, multi-runtime Claude)
  triggerte die RFC-9700-Replay-Revocation, die bei JEDEM Retry alle aktiven
  Access-Tokens der Kette killte (auch frisch rotierte) → Introspektion
  (`/v1/me`) 401 → tools/list leer, permanent. Fix in
  `oauth_service.exchange_refresh`: Reuse außerhalb der Grace wird nur noch
  abgelehnt (`invalid_grant` + Warn-Log), keine Ketten-Revocation mehr;
  Rotation/Grace/Single-Use unverändert, Deprovisioning killt weiterhin die
  Kette. Zusatzbefund dokumentiert: die Revocation kappte nie die
  Refresh-Kette und stoppte daher keinen Dieb. Details:
  `.claude/plan/2026-07-05-1200_oauth-refresh-reuse-no-chain-kill.md`,
  DECISIONS 2026-07-05. **DoD grün:** ruff/mypy (betroffene Module), 788 pytest
  (API+MCP gegen echtes Postgres, Stale-Reuse-Regressionstest neu),
  `oauth_smoke.py onprem` alle Checks, Repro-Skript zeigt Kette-überlebt.

- **Fix: Dashboard-Status-Verteilung = aktueller Status (2026-07-02), Branch
  `claude/code-agent-setup-qh480c`:** Die Donut-`status_distribution` zählte alle
  `*_version`-Zeilen nach Status — überholte Alt-Versionen (das `inactive` einer
  abgelösten Vorversion) blähten den Inaktiv-Topf auf, sodass das Dashboard
  „Inaktiv (N)" zeigte, der Listen-Filter aber (korrekt) nichts. Fix in
  `dashboard_repository`: die drei Distribution-Queries zählen jedes Aggregat
  jetzt GENAU EINMAL nach dem Status seiner aktuellen Version (`DISTINCT ON` +
  höchste Version im Default-Locale-Track) — identisch zu `_select_current`/der
  Listen-Sicht. Konsequenz (bewusst): die KPIs leiten sich aus der Distribution
  ab, daher zählt ein aktives Aggregat mit offenem Draft jetzt als „Entwurf"
  (nicht „Aktiv") — konsistent mit Liste + Donut. `test_dashboard_endpoint`
  angepasst. **DoD grün:** ruff clean, mypy 226, Python 660 pytest (Dashboard-
  Tests gegen echtes Postgres verifiziert).
- **MFA-Login-Step-up (2026-07-01), Branch `claude/code-agent-setup-2zrtxb`:**
  Bugfix — Admin-Aktionen forderten trotz eingerichtetem TOTP `aal2`, weil der
  Login keinen MFA-Challenge-Schritt hatte (Enrollment hob nur die aktuelle
  Session; nach neuem Tab/Ablauf/Re-Login wieder `aal1`, kein Weg zurück).
  Backend-Gate `require_aal2` war korrekt. Fix im Web-Login: `SessionProvider`
  prüft nach `signInWithPassword` via `mfa.getAuthenticatorAssuranceLevel`, ob
  Step-up fällig ist, und hält eine `aal1`-Session mit fälligem zweitem Faktor
  zurück (`apply()` committet sie nicht); `LoginPage` zeigt dann ein TOTP-Feld
  und fährt `mfa.challenge` + `mfa.verify` → `aal2`. `signIn` liefert jetzt
  `{ mfaRequired }`. i18n `auth.login.mfa.*` (de+en). Doku `docs/mfa-admin.md`.
  DoD grün: lint 0 Errors, tsc, 450 Tests, build. Plan:
  `.claude/plan/2026-07-01-1200_mfa-login-step-up.md`.
- **Listen-Status-Filter + Quick-Filter (2026-07-01), Branch
  `claude/code-agent-setup-qh480c`:** Alle vier Listen-Seiten (Personas,
  Playbooks, Resources, System-Prompts) bekommen eine einheitliche, URL-
  synchronisierte Filterleiste — reines Frontend, `current_status`/
  `has_pending_draft` kamen schon aus den List-Endpoints. Neu:
  `@/lib/listFilter.ts` (reine Logik: `needsAttention` = draft ∪ review ∪
  pending-draft, `countByStatus`, `matchesStatusFilter`), Hook
  `@/hooks/useListFilters` (kombinierbare Facetten Status+Freitext+Tag+Typ,
  Query-Keys `?status=&q=&tag=&type=`, faceted counts), Shared-Components
  `@/components/data/StatusBadge` (Status-Punkt+Label je Zeile, „Entwurf offen"-
  Marker) und `@/components/data/ListFilterBar` (Status-Quick-Chips mit Zähler,
  inkl. akzentuiertem „Braucht Aufmerksamkeit (N)"). Dashboard-`StatusDonut`-
  Legende verlinkt jetzt auf die vorgefilterte Liste (`hrefFor`). i18n
  `data.filter.*` (de+en). DoD grün: lint 0 Errors, tsc, 422 Tests, build.
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

- E2E-Gate bleibt Soft, bis die CI-Infra dauerhaft stabil ist.

## Nächste Schritte (nicht-Code, manuell beim Owner)

1. CI-Billing klären **oder** direkt auf Public flippen.
2. GitHub-Settings: Description, Topics, Issues/Discussions/Security-Advisories,
   Branch-Protection (CI-grün-Required erst nach CI-Fix).
3. CLA-Assistant aktivieren.
4. Visibility Private → Public (finaler Flip durch den Owner).
