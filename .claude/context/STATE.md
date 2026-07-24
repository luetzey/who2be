# STATE — Wo stehen wir (Snapshot, pro Run überschrieben)

_Stand: 2026-07-24_

Ist-Zustands-Snapshot, kein Changelog. Die Umsetzungs-Historie (per-Run-Details,
Branch-Namen, DoD-Belege) lebt in `.claude/plan/*` (Status-Übersicht:
[`.claude/plan/README.md`](../plan/README.md)) und den gemergten PRs.

## Funktioniert (Ist-Zustand)

### Kern-App (Phase 1–3)

- Tenancy (`User → org_member → Organization → Workspace → Entity`), API hart
  auf `/v1/workspaces/{ws_id}/…`; Status-Workflow draft→review→active→inactive
  pro Version + Dashboard; RBAC `admin > editor > viewer` (ADR-0023) +
  Magic-Link-Invitations. Pläne:
  `.claude/plan/2026-05-27-1921_phase-2-vollwertige-app.md`,
  `.claude/plan/2026-05-29-1900_phase-3-ux-polish.md`.
- Resources + BlockNote-Insel (ADR-0022), Placeholder-Pills (ADR-0025),
  Composite-Playbooks/Persona-Modi/Resource-Tags (ADR-0024,
  `docs/agent-axes.md`), Content-i18n (ADR-0027), Einzel-Delete/-Export
  (ADR-0032), Account-Lifecycle + DSGVO-Purge/-Export.
- Listen-UX mit URL-Filtern (`useListFilters`/`ListFilterBar`: Status/Agent/
  Tag/Typ/Gruppierung), Playbooks- + Dashboard-Design-Refresh (Pläne
  2026-07-11/-12), MFA-Login-Step-up (`docs/mfa-admin.md`).
- Reload-sichere Deep-Links: `SessionProvider` exponiert `sessionLoaded`,
  `RequireAuth` wartet den Session-Bootstrap ab (Ladeanzeige statt sofortigem
  `/login`-Redirect) und gibt beim echten Logout die Ziel-URL als `?next=` an
  die LoginPage weiter — vorher warf jeder Reload den User aufs Dashboard.
- Dashboard-Aufmerksamkeits-Band zeigt neben offenen Entity-Reviews auch
  pending Memory-Vorschläge (ADR-0044, Link → Agents) und System-Prompt-
  Templates in Review (Link → `/system-prompts?status=review`); KPI-Felder
  `pending_memories`/`pending_system_prompts` (Plan
  `.claude/plan/2026-07-22-1650_dashboard-attention-memories-system-prompts.md`).
- Agenten-Übersicht zeigt pro Agent offene Gedächtnis-Vorschläge:
  List-Enrichment `pending_memory_count` (Batch-Aggregat, kein N+1) +
  klickbarer Aufmerksamkeits-Pill → Deep-Link `#memory` scrollt zur
  Gedächtnis-Sektion der Detail-Seite und hebt sie kurz hervor (Plan
  `.claude/plan/2026-07-24-1623_agents-pending-memory-badge.md`).

### MCP + OAuth

- MCP-HTTP-Transport (ADR-0034) + OAuth-2.1-Remote-Connector (ADR-0036,
  per-Agent-URL `?agent=<uuid>`); Refresh-Reuse reject-only statt
  Ketten-Revocation (DECISIONS 2026-07-05); OAuth-Smoke beide Editionen grün.
- 57 Tools: Read + Write (ADR-0030), `search` (ADR-0037), Versions-/
  Discovery-Tools, System-Prompt-Tools (ADR-0040), feinkörnige
  Agent-Schreibrechte inkl. Rate-Limit (ADR-0039). `tools/list` pro Agent
  policy-gefiltert (fail-open, SSoT `who2be_models.tool_requirements`,
  ADR-0042, PR #305) — neue Tools brauchen einen Mapping-Eintrag.

### Builder

- Managed Builder-Agent (Persona mit 3 Modi, 6 Playbooks, Konventions-
  Resource) + Managed-Lock, Deep-Copy-Duplizieren, Content-Start-Sync
  (`BUILDER_CONTENT_VERSION`, Stand 11 = `external_tool_write` +
  Playbook „External Tool anlegen & pflegen" + Konventions-Sektion;
  Stand 10 = Memory `suggest`/`recommended`). Befähigung + UI-Polish:
  PR #301/#302; Richtungsentscheidungen in DECISIONS 2026-07-09/-10/-11
  und 2026-07-21 (Memory-Triage/-Guard bewusst UI-only). Plan:
  `.claude/plan/2026-07-21-0810_builder-external-tool-write.md`.

### Feedback-Flywheel (ADR-0038)

- Append-only `usage_event` + `agent_feedback`, Triage
  (`feedback_resolution`), Posteingang inkl. System-Feedback
  (`report_problem`), Hard-Delete, Capability `feedback_resolve` +
  MCP-Tool `resolve_feedback`.

### Agent-Memory (ADR-0044)

- Kuratiertes Langzeitgedächtnis pro Agent: `memory_mode`
  off<read_only<suggest<auto + Freigabe-Schleuse pending→Triage→active;
  MCP `search_memory`/`list_memories`/`save_memory`, Laufzeit-Einbindung via
  `get_persona`, Placeholder-Kind `memory`; Injection-Wächter konfigurierbar
  (`memory_guard`, PR #327–#329). Pläne:
  `.claude/plan/2026-07-18-1500_agent-memory.md` + 2026-07-19-*.

### External Tools (ADR-0043)

- Versionierte Aggregate `external_tool` (instruktiv, Alias-Referenz),
  Placeholder `tool-ref` mit Fetch-Time-Expansion, 6 MCP-Tools + Web-Features
  (PR #316; Plan `.claude/plan/2026-07-18-1315_external-tools-tool-ref.md`).

### Editionen / Deploy

- Ein Codebase, zwei Build-Profile (ADR-0028/0029): `org_entitlement` als
  SSoT, On-Prem via `WHO2BE_LICENSE_KEY`, Billing build-isoliert
  (`packages/billing`, Web via `VITE_WHO2BE_EDITION`). Deploy
  `deploy/hetzner` (Caddy `api.`/`app.`/`mcp.`, `--profile mcp-http`).

### Standards / CI

- Standards-Schicht (`docs/standards/`, `AGENTS.md`, `.claude/context/`),
  FSL-1.1 + CONTRIBUTING/SECURITY (Public-Switch vorbereitet), OSS-Lizenz-
  Gates (ADR-0033), Test-Pyramide + Coverage-Ratchet (ADR-0041);
  Security-Findings Phase 1+2 alle Closed.
- Standards-Review 2026-07-08: WP-1–8 umgesetzt
  (`docs/standards-review-2026-07-08.md` §3); heutiger Lauf s. u.

## In Arbeit

- **Standards-Review 2026-07-20** (`docs/standards-review-2026-07-20.md`,
  PR #331): Phase A mit 12 Prüf-Agenten; Phase B Wellen 1–3 umgesetzt
  (SEC-1/2/3, LIC-1, DEP-1/2/6, LIC-4, OSS-2, FE-1/10/11, Kosmetik-Sweep,
  GIT-8, Memory-Pflege). **DoD:** Python 1155 pytest / Coverage 89,74 %;
  Web 912 Vitest / Branches 81,07 %; alle Gates lokal grün.
- OAuth-Connector: E2E mit echtem Claude/ChatGPT-Client offen; TTL-Cleanup
  der OAuth-Tabellen, optionale Audience-Trennung, aal2-Consent (Phase 2).

## Bekannte Probleme

- **CI-Gate seit 2026-07-19 tot** (GitHub-Actions-Billing, Owner-Punkt): alle
  Runs scheitern nach ~2 s ohne Logs — kein Code-Problem; lokale DoD-Nachweise
  ersetzen das Gate interim (PR-Template).
- E2E-Gate bleibt Soft, bis die CI-Infra dauerhaft stabil ist.
- Offene Owner-Entscheidungen: `docs/standards-review-2026-07-20.md` §4
  (ADR-0002 enforce vs. amend, Branch-Protection/Merge-Strategie,
  On-Prem-RLS, Cloud-Image-Deploy, LIC-1-Mechanik, coverage.all/E2E/CLA).

## Nächste Schritte (nicht-Code, manuell beim Owner)

1. Actions-Billing klären (entsperrt das CI-Gate) **oder** direkt auf Public
   flippen.
2. GitHub-Settings: Branch-Protection, Auto-delete head branches,
   Merge-Strategie, Description/Topics/Discussions.
3. CLA-Assistant aktivieren; Visibility Private → Public (finaler Flip).
