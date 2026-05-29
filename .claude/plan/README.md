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
| `2026-05-27-1935_license-fsl-setup.md` | FSL-1.1-Apache-2.0 als Lizenzmodell + CLA — User-Entscheidungen offen |
| `2026-05-27-2028_public-switch-github-repo.md` | Repo privat → öffentlich; hängt auf Lizenz + CSP-Pass + Security-TODOs |
| `2026-05-28-0528_enterprise-license-management.md` | Code-Hooks-only; aktiviert bei erstem qualifizierten Lead |

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
