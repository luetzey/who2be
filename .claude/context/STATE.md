# STATE — Wo stehen wir (Snapshot, pro Run überschrieben)

_Stand: 2026-07-25_

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
- **Sprache als durchgängiges Konzept (ADR-0045, ersetzt UI-Teil von
  ADR-0027; PR #357, Issues #348–#356):** ein Element = eine Sprache
  (`locale` auf der Identitäts-Zeile aller 5 Content-Typen, Migration 0069;
  System-Prompts erstmals mit Sprachwahl), Reads locale-agnostisch,
  `?locale=` als Listenfilter, `LocaleBadge` + Sprachfilter in der Web-UI,
  Workspace-`content_locale` bei Anlage (vorbelegt aus UI-Sprache,
  Personal-Workspace aus `preferred_locale`), automatische
  Output-Sprachanweisung im Agent-Renderer (`services/agent_language.py`),
  MCP-Tools mit locale-Metadatum + Builder-Sprach-Tagging, komplettes
  EN-Rollout-Paket (`repositories/builder_content.py` + `repositories/en/`,
  14 Sidecars) mit locale-bewusstem Seeding/Sync
  (`BUILDER_CONTENT_VERSION = 12`). Plan
  `.claude/plan/2026-07-24-1900_sprache-vertiefen-ein-element-eine-sprache.md`.

### MCP + OAuth

- MCP-HTTP-Transport (ADR-0034) + OAuth-2.1-Remote-Connector (ADR-0036,
  per-Agent-URL `?agent=<uuid>`); Refresh-Reuse reject-only statt
  Ketten-Revocation (DECISIONS 2026-07-05); OAuth-Smoke beide Editionen grün.
- 58 Tools: Read + Write (ADR-0030), `search` + `search_content`
  (ADR-0037/0046), Versions-/
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

### Release-Vorbereitung / Pre-Publish-Nachweis (2026-07-22)

- **Release-Audit** (Repo-Publish-Flow, Issues #338–#341): Ergebnis „noch
  nicht release-fertig" — Blocker waren npm-audit, fehlende NOTICES und der
  tote CI-Nachweis; Wellen 1–2 umgesetzt (dieser Run), Welle 3 (#341) wartet
  auf CI-Reaktivierung.
- **Secrets-Gate bestanden:** kein Secret im Tree (nur Dev-/Test-Platzhalter
  und `${VAR}`-Injektionen); History sauber — nie `.env`/`.pem`/`.key`
  committet, gitleaks + 8 Pattern-Scans über alle Commits negativ
  (`.claude/plan/2026-05-27-2028_public-switch-github-repo.md`); **kein
  History-Rewrite nötig**.
- **npm-audit-Triage:** 3 CVEs (tar critical, undici + brace-expansion high)
  waren ausschließlich Dev-Tooling (eslint-Kette, jsdom, license-checker/
  node-gyp); `npm audit --omit=dev` war durchgehend clean → kein
  Runtime-Risiko. Per `npm audit fix` (nur Lockfile, 12 transitive Pakete)
  geschlossen; `npm audit` jetzt 0 Findings, Web-DoD danach grün
  (917 Tests, Coverage Statements 86,96 %/Branches 81,14 %).
- **Publish-Artefakte:** CODE_OF_CONDUCT.md (Contributor Covenant 2.1),
  ROADMAP.md, CHANGELOG.md, README-Ausbau, `LICENSE.md → LICENSE`,
  `THIRD-PARTY-LICENSES.md` + Generator
  (`scripts/gen_third_party_notices.sh`, OSS-1/ADR-0033).

## In Arbeit

- **Semantische Suche & Passage-Retrieval (ADR-0046)** — vollständig umgesetzt
  (Wellen 1–3).
  - *Welle 1:* `content_chunk` (Migration 0070, Schnitt an Heading-Blöcken,
    FTS-Config pro Sprache), Chunk-Aufbau im Transition-Pfad, `search_content`
    als REST + MCP-Tool (Passagen statt Aggregate), Backfill-CLI
    `who2be-retrieval-backfill`, plus zwei behobene Fehler der bestehenden Suche
    (Read-Scope hinter dem `LIMIT`; 403 auf Fremdtypen).
  - *Welle 2:* `content_vector` (Migration 0071, **fail-soft** ohne pgvector),
    asyncpg-Vektor-Codec mit dynamischer Schema-Auflösung, `EmbeddingPort` +
    lokaler fastembed-Adapter in der optionalen Dep-Gruppe `embeddings`,
    Hybrid-Ranking per RRF, `mode`-Parameter (`auto|text|semantic|hybrid`),
    Vektor-Backfill. Postgres-Images lokal/CI/Testcontainers auf
    `pgvector/pgvector:pg16`.
  - *Welle 3:* `content_vector` auf `agent_memory` (Migration 0072, fail-soft),
    `search_active` von der lexikografischen `ORDER BY`-Kaskade auf
    **RRF-Fusion über vier Zweige** umgebaut (FTS, ILIKE, Trigram, Vektor),
    semantischer Zweig im Dedup-Wächter, best-effort-Embedding im
    Laufzeit-Schreibpfad, Memory-Vektor-Backfill. Der MCP-Docstring, der seit
    ADR-0044 „semantisch" versprach, ist damit eingelöst.
  - Memory hat zwei komplementäre Testdateien: die Baseline hält fest, was der
    lexikalische Pfad kann und wo seine Grenzen liegen; `test_memory_semantic`
    belegt, dass der Vektor-Zweig genau diese Grenzen löst — ohne die
    lexikalischen Fähigkeiten zu verdrängen.
  - **DoD:** Python 1256 pytest / Coverage ~90 %; ruff + format-check + mypy
    grün; Web unberührt (keine Änderung unter `apps/web/`).
  - **Offen:** Kalibrierung der drei Schwellen (`_MIN_VECTOR_SIMILARITY` je
    Korpus, `_DEDUP_VECTOR_SIMILARITY`) gegen das reale Modell — der
    Modell-Download ist in der Entwicklungsumgebung per Netz-Policy gesperrt.
    Die Retrieval-Mechanik ist gegen deterministische Test-Vektoren mit
    bekannter Geometrie belegt, die Modell-Qualität nicht.
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

Als Owner-Checkliste getrackt in Issue #338 (Welle 3 der Release-Mechanik
in #341):

1. Actions-Billing klären (entsperrt das CI-Gate) **oder** direkt auf Public
   flippen.
2. GitHub-Settings: Branch-Protection, Auto-delete head branches,
   Merge-Strategie, Description/Topics/Discussions.
3. CLA-Assistant aktivieren; Visibility Private → Public (finaler Flip).
