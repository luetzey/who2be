# Plan-Ordner — Status-Übersicht

Jede Session-Arbeit wird hier als eigenes Plan-File abgelegt (Zeitstempel-Slug).
Diese README ist die **lebende Status-Übersicht** — pro Plan-File kurz festgehalten,
ob es abgeschlossen, aktiv oder archiviert ist. Einzelne Plan-Files tragen den
Status zusätzlich in ihrem eigenen Header, sind aber nicht alle rückwirkend
aktualisiert.

Bei Konflikt zwischen Plan-Header und dieser Übersicht **gewinnt die Übersicht**
(wird mit jedem Phase-Closeout-PR aktuell gehalten).

## Aktiv (kein PR offen, aber Backlog-Eintrag)

| Datei | Inhalt |
|---|---|
| `2026-05-27-1935_license-fsl-setup.md` | FSL-1.1-Apache-2.0 als Lizenzmodell — LICENSE.md/CONTRIBUTING liegen; CLA-Aktivierung offen (Owner) |
| `2026-05-27-2028_public-switch-github-repo.md` | Repo privat → öffentlich; finaler Flip + GitHub-Settings beim Owner (siehe STATE.md §Nächste Schritte) |
| `2026-05-28-0528_enterprise-license-management.md` | Code-Hooks-only; aktiviert bei erstem qualifizierten Lead |
| `2026-09-05-1520_cloud-launch-readiness-inventar.md` | Cloud-Pfad als belegte Checkliste (WP-1 von #428, Issue #434); Zuschnitt WP-2…WP-6 vorgeschlagen, Deploy-Umbau + Live-Lauf offen (Owner) |
| `2026-09-05-1625_backlog-vorbereitungslauf.md` | Norm-Audit aller offenen Issues (10 von 12 ohne Abstriche), vier falsche Zeiger korrigiert (#450 Verifikations-Grep wirkungslos, #453/#429/#430 Zeilenbelege), #436 auf `needs-decision` (`errors.py` existiert bereits — zwei Fehler-Vokabulare?), #442 + PROJECT.md §Reihenfolge nachgezogen. Offen beim Owner: Weiche auf #436, PR #443 schließen, zwei belegte Funde ohne Issue |

## Blöcke seit 2026-05-30 (nachgeführt 2026-07-20)

Kompakte Status-Nachführung; Details + DoD-Belege in
[`.claude/context/STATE.md`](../context/STATE.md). Status: ✅ erledigt,
🔄 offen/teilweise. Die Feedback-/Builder-Lock-PR-Serien von Ende Juni
(`feat/feedback-*`, `feat/builder-*`, u. a. PR #272, #282) liefen ohne eigene
Plan-Dateien unter dem ai-native-Plan + ADR-0038.

| Plan-Datei | Thema | Status |
|---|---|---|
| `2026-05-30-*` + `2026-05-31-{1200,1400,1700,2030}_*` (8 Dateien) | Phase-3-Fix-Runden 2+3 (Agent-Prompt-Wellen, Autosave, Forms, Slash-Templates, Frontend-Standards-Cleanup) | ✅ |
| `2026-05-31-1630_composite-applied-modi.md` | Agenten-Achsen Track D/E: Composite-Playbooks (ADR-0024), Applied-via-Pill, Persona-Modi, Resource-Tags | ✅ |
| `2026-06-01-*`, `2026-06-02_pill-*`, `2026-06-02-1700_track-f-persona-pills-skills.md` | Pill-/Editor-Ausbau (Preview-Overlay, Popover, Persona-Modi im BlockNote, Placeholder-Pills ADR-0025) | ✅ |
| `2026-06-02-1349_feature-expansion-cloud-onprem-spaces-versioning.md`, `2026-06-02-1819_followups-rls-mollie-auth-fsl.md`, `2026-06-03-2030_cloud-launch-readiness.md` | Cloud/On-Prem-Ausbau, RLS/Mollie/Auth-Followups, Launch-Readiness | ✅ |
| `2026-06-03-2200_account-lifecycle-gdpr.md` | Account-Lifecycle + DSGVO-Purge/-Export | ✅ (Purge-Lücken neu: Audit WP-3) |
| `2026-06-04-1000_ux-fixes-i18n-embedding.md`, `2026-06-04-1200_i18n-content-model.md`, `2026-06-04_embedding-mode-resource-compose.md` | UX-Fixes, Content-i18n (ADR-0027), Embedding-Modus + Resource-Compose | ✅ |
| `2026-06-05-1200_build-isolation-entitlement-sources.md`, `2026-06-05-1311_compliance-de-saas-remediation.md` | Editionen/Entitlements (ADR-0028/0029), Compliance-Remediation (ADR-0031) | ✅ |
| `2026-06-05-1500_per-agent-mcp-tool-policy.md`, `2026-06-05-1500_single-element-delete-export.md` | Per-Agent-Tool-Policy; Einzel-Delete/-Export (ADR-0032) | ✅ |
| `2026-06-05-1700_test-pyramid-tdd.md` | Test-Pyramide + Coverage-Ratchet (ADR-0041, ex-0032) — PR #149 | ✅ |
| `2026-06-05-1930_coding-standards-audit-remediation.md` | Coding-Standards-Audit + OSS-Lizenz-Gates (ADR-0033) | ✅ |
| `2026-06-12-1200_seed-builder-default-agent.md`, `2026-06-13-1512_repo-review-remediation.md` | Builder-Seed (Default-Agent); Repo-Review-Remediation | ✅ |
| `2026-06-14-0810_public-switch-execution.md`, `2026-06-14-0832_notion-decoupling.md`, `2026-06-14-0947_llm-standards-materialization.md` | Public-Switch-Vorbereitung, Notion-Entkopplung, Standards-Schicht (`docs/standards/`, AGENTS.md, `.claude/context/`) | ✅ (finaler Public-Flip 🔄 Owner) |
| `2026-06-25-1200_mcp-dx-builder-coder.md`, `2026-06-25-1324_agent-connector-params.md` | MCP-DX (HTTP-Transport ADR-0034, Ein-Klick-Config); Per-Agent-Connector-URL (ADR-0036-Addendum) | ✅ |
| `2026-06-27-1100_ai-native-mcp-and-rights.md` | AI-native MCP: Tracks 1–4 (Versions-/Discovery-Tools, Search ADR-0037, Feedback-Flywheel ADR-0038, feinkörnige Rechte ADR-0039) | ✅ |
| `2026-06-27-1500_builder-system-prompt-tools.md` | Builder-System-Prompt-Tools (ADR-0040) — PR #266 | ✅ |
| `2026-06-27-1200_ux-axes-improvements-grouping.md` | UX-Achsen-Analyse (Draft-Discard, Schnellfreigabe, Gruppierung) | 🔄 weitgehend abgearbeitet (Welle 2026-08-20, Issues #391–#394); Rest: Draft-Discard (nach CI-Wiederbelebung), Quick-Release (Owner-Weiche), proaktive Pflichtfeld-Hinweise |
| `2026-07-01-1200_mfa-login-step-up.md` | MFA-Login-Step-up (TOTP-Challenge im Web-Login) | ✅ |
| `2026-07-02-1100_oauth-refresh-grace-window.md`, `2026-07-05-1200_oauth-refresh-reuse-no-chain-kill.md` | OAuth-Refresh-Fixes (Grace-Window; Reuse ohne Ketten-Revocation) + tools/list-Payload-Fix | ✅ |
| `2026-07-09-1556_builder-agents-ui-improvements.md` | Builder-Befähigung (Placeholder/Modi/Sub-Playbooks) + Agent-Filter + UI-Polish (Git-Diff, Trigger-Pills, Playbooks-Liste, Persona-Sektion), 6 WPs | ✅ (PR #301) |
| `2026-07-10-1524_mcp-per-agent-tool-filtering.md` | MCP `tools/list` pro Agent policy-gefiltert (ADR-0042, SSoT `tool_requirements`) | ✅ (PR #305) |
| `2026-07-11-1200_playbooks-uiux-redesign.md` | Playbooks-UI/UX-Redesign (Karten-Übersicht, Detail-Tabs, ReviewBanner) | ✅ |
| `2026-07-11-1500_dashboard-design-refresh.md`, `2026-07-12_design-refresh-corrections.md`, `2026-07-12_feedback-and-link-editors.md` | Design-Refresh Dashboard/System-Prompts/Agents/Resources/Feedback + Nachbesserungen; Link-Editoren + zentrales Feedback + Einzel-Feedback-Detail | ✅ (PR-Serie um #309/#310) |
| `2026-07-18-1315_external-tools-tool-ref.md` | Externe Tools + `tool-ref`-Placeholder (ADR-0043) | ✅ (PR #316) |
| `2026-07-18-1500_agent-memory.md` | Agent-Memory: Kurations-Schleuse, memory_mode, MCP-Tools, Laufzeit-Einbindung (ADR-0044) | ✅ (PR #324, Builder-Content v8: #325) |
| `2026-07-19-0600_memory-placeholder.md` | Placeholder-Kind `memory` (ADR-0044-Addendum) | ✅ |
| `2026-07-19-1030_memory-guard-config.md` | Injection-Wächter konfigurierbar (`memory_guard`, ADR-0044-Addendum 2) | ✅ (PR #329) |
| `2026-07-21-0810_builder-external-tool-write.md` | Builder-Content v11: `external_tool_write` in der Builder-Policy, Playbook „External Tool anlegen & pflegen", Konventions-Sektion, Sync-Link-Fix | ✅ |
| `2026-08-13-1200_agent-workarea-knowledge-base.md` | Agent WorkArea + Knowledge Base (unversionierte Subsysteme, MinIO-Blob-Store, SQLite-Tabellen-Store — ADR-0047/0048/0049), 20 WPs in 7 Wellen; WP1–WP20 umgesetzt inkl. Security-Review Phase 2, Retention-Sweeps, GDPR-Export und Compliance-Doku (PR #367). Offen: P1/P2-Backlog (TTL/Challenger/Drift, UI/Graph/semantische Suche) + manuelle Compose-Verifikation | ✅ umgesetzt (PR #367) |
| `2026-08-19-1500_stufe3-wa-render-tablestore.md` | Aufräumen Stufe 3: Render-/Entschärfungs-Helfer aus `wa_tables.py` nach `wa_render.py`; SQL-Bau aus `wa_rules.py` in `TableStore.reapply_category` — letzter offener Punkt aus dem Aufräum-Plan (nach Stufe 1 PR #380, Stufe 2 PR #381) | ✅ umgesetzt |
| `2026-08-19-1700_tabellen-ui-und-exporte.md` | Tabellen-UI in der WorkArea (Tab + TableDetailPage) + Export-Endpoints Tabellen (CSV/XLSX) und Notizen (Markdown/HTML + PDF-Druck); Security-Review 5 Findings behoben | ✅ umgesetzt |
| `2026-08-19-1805_refactor-web-dedup-status-actions.md` | Refactoring-Lauf Web-Dedup: StatusActionBar + Status-Lib nach `components/version/`, Entity-Buttons nach `components/entity/` (jscpd 2,94 % → 2,47 %, netto −2298 Zeilen) | ✅ umgesetzt |
| `2026-08-19-2110_repo-pflege-branches-tests.md` | Repo-Pflege: Branch-Hygiene (81 Branches klassifiziert → Owner-Issue #388), Dependabot-Triage (#368 gemergt, #245/#243/#242 geschlossen), E2E-Journeys scharf (4 fixme → aktiv) | ✅ umgesetzt (PR #387) |
| `2026-08-20-0813_repo-pflege-doku-struktur.md` | Repo-Pflege Doku & Struktur: Public-Artefakte englisch + aktuell (README/CHANGELOG/CONTRIBUTING/SECURITY/ROADMAP), Issue-Forms + SUPPORT.md + docs-Index + OpenAPI-Referenz, PROJECT.md auf Release-Vorhaben | ✅ umgesetzt (PR #389) |
| `2026-08-20-1031_repo-pflege-status-abhaken.md` | Repo-Pflege: Status-Nachführung (diese Übersicht + STATE.md), Abhak-Prüfung #338/#341, CI-Regression seit 2026-08-19 ~16:37 aufgedeckt + dokumentiert, Zusammenfassung offener Aufgaben | ✅ umgesetzt |
| `2026-08-20-1047_offene-aufgaben-abarbeiten.md` | Offene Aufgaben (codebar): #385 Skip-Guard (2 Dateien ohne `integration`-Marker), #384 Bump+Reformat (8 Pakete, Ruff-0.16-Markdown-Format), #341 WP-8-Teil (Version 0 → 0.1.0); Teil B = Owner-Schrittfolge | ✅ umgesetzt (PR #390) |
| `2026-08-20-1115_ux-backlog-welle-subagents.md` | UX-Backlog-Welle mit Sub-Agents (Issues #391–#394): StatusActionBar-Refactor Personas/Playbooks + E2E-Testid-Fix, MCP-Docstring-DX, Tag-Gruppierung Playbooks/Resources, Policy-Presets; Juni-Plan `2026-06-27-1200` damit abgearbeitet/überholt (Rest: Draft-Discard nach CI, Quick-Release = Owner-Weiche) | ✅ Wellen 1–2 (PR #390 gemergt) |
| _(ohne Plan-Datei — Ereignis-getrieben)_ | **Public-Day 2026-08-20:** Pre-Publish-Check (Secrets-Delta, Negativ-Liste, Branch-Bereinigung 74 Branches, Pitch-Dossier gesichert+entfernt), Owner-Flip auf Public, CI-Wurzelursache SHA-Pinning-Policy behoben (19 Actions gepinnt), E2E-Journeys in 3 Runden real grün (TOTP/aal2, Seeds, Selektoren), e2e hartes Gate, PR #390 gemergt, CHANGELOG 0.1.0 | ✅ (Tag/Release = Owner) |

Offen außerhalb der Plan-Dateien: Owner-Punkte aus
`docs/standards-review-2026-07-20.md` §4 sowie der dortige Folge-Backlog
(WP-14). Der dort führende Punkt „Actions-Billing → CI-Gate tot" ist seit
2026-08-16 erledigt (STATE.md §Standards / CI).

## Phase 3 — UX-Polish (alle ✅ Done)

Master: `2026-05-29-1900_phase-3-ux-polish.md` — siehe dortige PR-Tabelle.

- `2026-05-29-1817_3-0-models-migrations.md` — PR #57
- `2026-05-29-1850_3-A-backend.md` — PR #61
- `2026-05-29-1851_3-B-editor-forms.md` — PR #60
- `2026-05-29-1850_3-C-navigation-ux.md` — PR #58
- `2026-05-29-2030_3-D-invitation-magic-link.md` — PR #59

## Phase 2 — Vollwertige App (alle ✅ Done)

Master: `2026-05-27-1921_phase-2-vollwertige-app.md` — siehe dortige PR-Tabelle.

- `2026-05-28-1730_2.1a-1-tenant-migrations.md` — PR #38, #40
- `2026-05-28-1900_2.1a-2-tenant-api-schwenk.md` — PR #41 (+ #42 Follow-up)
- `2026-05-28-2026_2.1b-models-adrs.md` — PR #44
- `2026-05-28_2.1b-status-backend.md` — PR #46
- `2026-05-28-2036_2.1b-dashboard-backend.md` — PR #45
- `2026-05-28-2038_2.1b-status-dashboard-web.md` — PR #47
- `2026-05-28_2.2-resources-blocknote.md` — PR #48
- `2026-05-29-0953_2.3-0-rbac-models.md` — PR #49
- `2026-05-29-1130_2.3-A-rbac-gates.md` — PR #50
- `2026-05-29_2.3-B-invitations.md` — PR #51
- `2026-05-29-1130_2.3-C-members-web.md` — PR #52
- `2026-05-29-1400_repo-cleanup-post-phase-2.md` — Cleanup-PR (dieser)

## Phase 1 — MVP-Roadmap (alle ✅ Done — siehe `2026-05-24_who2be-mvp-roadmap.md`)

API-Fundament, Migration-Runner, Domänen-Layer, MCP, Web-UI, Auth-Bridge,
Settings-Tokens, Persona/Playbook-Editor, Linking-Hook, Local-Smoke,
Compose-Smoke-Pipeline, Rate-Limiting, JSON-Logs, Security-Review,
Compose-Layer, CI/CD-Deploy, Backend-Followups, Blueprint-v2, Cloud-Prep,
Cloud-Tauglichkeit (MS-2 bis MS-5).

- `2026-05-21-1354_api-fundament-config-db.md`
- `2026-05-21-1405_migrations-runner.md`
- `2026-05-21-1423_sql-migrationen-kern-tabellen.md`
- `2026-05-21-1610_pydantic-models.md`
- `2026-05-21-1645_auth-jwt-api-token.md`
- `2026-05-21-1730_persona-domaene.md`
- `2026-05-21-1815_playbook-domaene.md`
- `2026-05-21-1900_mcp-tools.md`
- `2026-05-21-1945_web-ui.md`
- `2026-05-24-1410_w1-auth-bridge-supabase-api-token.md`
- `2026-05-24-1450_w2-settings-tokens-page.md`
- `2026-05-24-1500_w3-persona-editor-versions.md`
- `2026-05-24-1510_w4-playbook-editor-versions.md`
- `2026-05-24-1520_w5-persona-playbook-linking-hook.md`
- `2026-05-24-1535_w6-local-smoke-doc.md`
- `2026-05-24_who2be-mvp-roadmap.md`
- `2026-05-25-1047_compose-smoke-pipeline.md`
- `2026-05-25-1744_ms3-h1-rate-limiting.md`
- `2026-05-25-1842_ms3-h2-json-logs.md`
- `2026-05-25-1909_ms3-h3-security-review.md`
- `2026-05-25-2008_ms2-c3-app-compose.md`
- `2026-05-25-2021_ms2-c2-supabase-stack.md`
- `2026-05-25-2032_ms2-c4-cicd-deploy.md`
- `2026-05-26-0551_backend-followups-f02-f09.md`
- `2026-05-26-0845_who2be-blueprint-v2.md`
- `2026-05-26-0942_h5-c5a-c5b-cloud-prep.md`
- `2026-05-26-1010_cloud-tauglich-batch-h6-h8-ms5.md`

## Frontend-Umbau Phasen 6–8 (✅ Done — siehe `docs/frontend/migration-plan.md`)

- `2026-05-26-1521_frontend-ux-states-a11y-tokens.md`
- `2026-05-26-1530_web-ui-design-system-tailwind-shadcn.md`
- `2026-05-27-0714_frontend-phase-6-theme-toggle-oklch.md`
- `2026-05-27-0900_frontend-phase-7-component-catalog.md`
