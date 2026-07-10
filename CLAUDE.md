# CLAUDE.md
This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Diese Datei definiert die REPO-FAKTEN + repo-spezifischen Konventionen
(Struktur, Befehle, Code-Style, Etikette, Security) — verbindlich fuer dieses
Repo. (Optionale persoenliche Agent-Workflows gehoeren in eine lokale, nicht
eingecheckte `CLAUDE.local.md`.)

## LLM-/Agent-Kontext (zuerst lesen)

- **[`AGENTS.md`](AGENTS.md)** — tool-agnostischer Einstieg (Lese-Reihenfolge).
- **[`docs/standards/`](docs/standards/)** — stehende Engineering-Standards
  (Architektur, Coding, Testing, Security, Frontend, Compliance) + die
  **Arbeitsmethode** (`engineering-method.md`). Generisch; diese CLAUDE.md +
  Skills sind die repo-spezifische Konkretisierung und haben Vorrang.
- **[`.claude/context/`](.claude/context/)** — persistentes Projekt-Gedaechtnis
  (PROJECT / ARCHITECTURE / DECISIONS / STATE) gegen Session-Drift. **Vor dem
  Planen lesen, nach jedem Run pflegen** (STATE immer; DECISIONS bei jeder
  Entscheidung; ARCHITECTURE/PROJECT nur bei Struktur-/Ziel-Aenderung).

# Projektkontext

Who2Be — selbst-gehostete AgentDB fuer versionierte Persona- und Playbook-Verwaltung.
Mono-Repo. Diese Datei wird jede Session geladen — kurz halten. Stack-Details siehe
Skills `python-conventions` und `react-conventions`, Projekt-Profil siehe
`docs/CLAUDE-PROFILE.md`.

## Aktueller Stand

**Führende Quelle ist [`.claude/context/STATE.md`](.claude/context/STATE.md)**
(pro Run gepflegt). Dieser Abschnitt ist nur der grobe Rahmen und bleibt
bewusst knapp — Details, DoD-Belege und PR-/Plan-Verweise stehen in STATE.md
und `.claude/plan/README.md`.

**Phase 2 — Vollwertige App (2026-05-29):** Tenancy
(`User → org_member → Organization → Workspace → Entity`, API hart auf
`/v1/workspaces/{ws_id}/...`), Status-Workflow pro Version + Dashboard,
Resources + BlockNote-Insel (ADR-0022), Multi-User-RBAC
(`admin > editor > viewer`, ADR-0023) + Invitations.

**Phase 3 — UX-Polish (2026-05-29):** Status-Default `draft`, Section-aware
Block-Refs + Reverse-Lookups, Editor-/Form-Polish, WorkspaceSwitcher +
Status-Action-Bar + Backlinks, Magic-Link-Invitation-Onboarding. Master-Plan:
`.claude/plan/2026-05-29-1900_phase-3-ux-polish.md`.

**Danach (2026-05-31 – 2026-06-05):** Agenten-Achsen (Composite-Playbooks
ADR-0024, Persona-Modi, Resource-Tags — `docs/agent-axes.md`); MCP-Write-Tools
(ADR-0030); Einzel-Element-Delete/-Export (ADR-0032); Editionen/Entitlements
(ADR-0028/0029).

**Stand seit 2026-06 (Details: STATE.md):** OAuth-2.1-Remote-MCP-Connector
(ADR-0036) auf MCP-HTTP-Transport (ADR-0034); Search (ADR-0037);
Feedback-Flywheel + Triage/Posteingang (ADR-0038); feinkörnige
Agent-Schreibrechte inkl. Rate-Limit (ADR-0039); Builder-System-Prompt-Tools
(ADR-0040); Builder-Managed-Lock + Deep-Copy-Duplizieren + Content-Start-Sync;
MFA-Login-Step-up; OSS-Lizenz-Gates (ADR-0033); Public-Switch-Vorbereitung
(FSL-1.1, Standards-Schicht).

Offene/nächste Blöcke: siehe STATE.md §Bekannte Probleme (u. a. Web-Coverage-PR
gegen roten `main`-CI-Job) und §Nächste Schritte (Public-Switch, CLA,
CI-Billing) sowie `docs/standards-review-2026-07-08.md` (WP-1–9).

## Struktur

- `apps/api/` — FastAPI-Backend (REST, `/v1/workspaces/{ws_id}/...`)
- `apps/mcp/` — FastMCP-Server. Read-Tools (`get_persona`, `list_playbooks`,
  `fetch_playbook`, `list_resources`, `fetch_resource`, `fetch_agent`,
  `list_triggers` — workspace-aware, filtern auf `status='active'`) plus
  Write-Tools (ADR-0030: create/update/transition/restore + Link-Setter fuer
  Persona/Playbook/Resource/Agent; Autorisierung serverseitig). Dazu:
  `search` (ADR-0037), `whoami`, Versions-/Discovery-Tools (`find_usages`,
  `list_versions`, `get_version`, `diff_versions`), Feedback-Flywheel
  (`record_usage`, `submit_feedback`, `get_feedback`, `report_problem` —
  ADR-0038) und System-Prompt-Tools (`list/get/create/update/restore/
  transition_system_prompt` — ADR-0040). `tools/list` ist pro Agent
  policy-gefiltert (`PolicyFilterMiddleware`, fail-open; SSoT-Mapping
  `who2be_models.tool_requirements` — ADR-0042); neue MCP-Tools brauchen
  dort einen Mapping-Eintrag
- `apps/web/` — React/TypeScript-Web-UI (Vite, Tailwind v4, shadcn-Primitives,
  BlockNote-Insel für den Resource-Editor; Designsprache "Warm Citrus" laut
  `docs/frontend/design-language.md`)
- `packages/models/` — geteilte Pydantic-Models, von API und MCP importiert
- `packages/billing/` — **optionales Cloud-Billing-Paket** (`who2be-billing`:
  Mollie-Checkout/-Webhooks, Tarif-Logik, `manual_override`). Build-Zeit-isoliert
  (ADR-0029): nur die Cloud-Edition zieht es (`uv sync --group billing`,
  Docker-Target `runtime-cloud`); das On-Prem-Artefakt enthaelt es physisch nicht.
  Der Kern (`apps/api`) haengt nicht davon ab und importiert es nie statisch.
- Supabase (Postgres) als DB; lokal via Docker-Compose, Ziel-Hosting Hetzner

Python ist ein uv-Workspace im Repo-Root (`pyproject.toml` → `members`). Die
Python-Pakete (`who2be-api`, `who2be-mcp`, `who2be-models` + optional
`who2be-billing`) sind editierbar verlinkt; `models` ist die geteilte
Abhaengigkeit zwischen API und MCP, `who2be-billing` haengt einseitig am Kern.

**Editionen / Entitlements (ADR-0028/0029):** Ein Codebase, zwei Build-Profile.
`org_entitlement` ist die einzige gelesene SSoT; geschrieben wird sie nur von
benannten Quellen (`mollie`/`cloud`/`manual_override`/`signed_license`), nie von
der Read-App. On-Prem entsteht ein Entitlement ausschliesslich aus dem
K_pub-verifizierten `WHO2BE_LICENSE_KEY` (env-validiert, kein Tabellen-Write);
Cloud-Entitlements nur ueber den Billing-Dienst, Ausnahme ist der befristete,
auditierte Admin-Override. Build-Isolation auch im Web (`features/billing` per
`VITE_WHO2BE_EDITION` aus dem On-Prem-Bundle tree-geshaked).

## Befehle

Python (uv-Workspace im Repo-Root):

- Dependencies: `uv sync --group billing` (inkl. Cloud-Billing-Paket; ohne
  `--group billing` laeuft der On-Prem-Kern, dann fehlen die Billing-Tests)
- Tests: `uv run pytest --cov --cov-fail-under=85` (Coverage-Gate wie in CI —
  lokal = CI, Coverage-Ratchet)
- Einzeltest: `uv run pytest apps/api/tests/test_health.py::test_health`
- Lint: `uv run ruff check .`
- Format: `uv run ruff format .`
- Typecheck: `uv run mypy .`
- API starten: `uv run uvicorn who2be_api.main:app --reload`
- MCP starten: `uv run python -m who2be_mcp.server`

Web (in `apps/web/`):

- Dependencies: `npm ci`
- Dev-Server: `npm run dev`
- Tests: `npm run test:coverage` (Vitest mit Coverage-Gate wie in CI — lokal =
  CI, Coverage-Ratchet); Einzeldatei: `npm test -- src/App.test.tsx`
- Lint: `npm run lint`
- Typecheck: `npx tsc --noEmit`
- Build: `npm run build`

Lokale Infrastruktur: `docker compose up -d` (Postgres-Stub; wird in Phase 0/T1
durch self-hosted Supabase ersetzt). Env-Vorlage: `.env.example` → `.env`.

CI (`.github/workflows/ci.yml`) faehrt beide Stacks: Python (ruff/mypy/pytest) und
Web (lint/tsc/test/build). Vor dem Push lokal gegenpruefen.

## Code-Style (nur Abweichungen)

- Python: Type Hints Pflicht; Pydantic an API-/MCP-Grenzen; kein blankes `except:`.
  ruff `line-length = 100`, mypy `strict`.
- TypeScript: strikt, kein `any` ohne Begruendung; funktionale Komponenten + Hooks;
  bestehende Patterns wiederverwenden.

## Frontend-Standards (repo-spezifisch)

Die tragenden Prinzipien (Single-Source pro Entscheidung, Design-Tokens,
Komponenten-Bibliothek, Layout-Primitives, fuenfschichtige UI-Architektur,
UX-Kohaerenz, A11y-Minimum, keine Utility-Suppe) gelten projektweit. Diese
Sektion + `docs/frontend/design-language.md` sind die verbindliche Quelle und
fuellen die repo-spezifischen Stellen (Stack/Pfade/Header-Ebene).

**Designsprache (verbindlich):** [`docs/frontend/design-language.md`](docs/frontend/design-language.md)
— Token-Werte, Komponenten-Anwendungsmuster, Motion-Tokens und der
AI-Agenten-Vertrag. **Bei jeder UI-Aenderung zuerst diese Datei lesen.**

### Stack

- Framework: Vite 7 + React 18, TypeScript `strict` (`apps/web/tsconfig.app.json`).
- Routing: `react-router-dom@7` (kein Next-App- oder Pages-Router).
- Tailwind v4 via `@tailwindcss/vite`: Tokens in `src/styles/globals.css`
  (`@import "tailwindcss"` + `@theme inline`). **Kein** `tailwind.config.*`.
- shadcn-Primitives unter `@/components/ui/*` (cva-Varianten, Radix-Slot).
- Klassen-Merge `cn()` aus `@/lib/utils` (`clsx` + `tailwind-merge`).
- Forms: `react-hook-form` + `zod` + shadcn `Form`-Wrapper.

### Ordnerbaum (apps/web/src)

- `features/<domain>/{pages,components,hooks?,lib?}` — Barrel exportiert nur Pages.
- `components/ui/` — Primitives (shadcn-konform), keine Domaenenlogik.
- `components/layout/` — `AppShell`, `PageHeader`, `Container`, `Section`, `Stack`.
- `components/data/` — `DataList`, `DataView`, `EmptyState`, `ErrorAlert`, `LoadingState`.
- `lib/` — Utilities (u.a. `utils.ts` mit `cn()`).
- `styles/globals.css` — einzige CSS-Datei, einzige Token-Quelle.
- `test/` — Vitest-Setup; Tests neben dem Modul (`*.test.tsx`).

### Lint-Gates (ESLint-error, siehe `apps/web/eslint.config.js`)

- Direkte `<button>`/`<input>`/`<textarea>`/`<a>` sind `error` in
  `src/features/**`, `components/{layout,data}/**`, `app/**` — stattdessen
  Primitives aus `@/components/ui/*` bzw. `<Link>` aus `react-router-dom`.
- Cross-Feature-Deep-Imports sind `error`
  (`@/features/<a>/{pages,components,hooks,lib}/* → features/<b>/...`);
  Geteiltes nach `@/components/` oder `@/hooks/` hochziehen.
- `tailwindcss/no-contradicting-classname` = `error`,
  `tailwindcss/classnames-order` = `warn`.

### Konvention (nicht ESLint-erzwungen)

- Forms/Dialoge/Dropdowns ebenfalls nur via `@/components/ui/*` (shadcn-
  `Form` mit `react-hook-form` + `zod`).
- Keine `#hex`-Literale, keine `px`-Werte im JSX; Werte ueber Tokens in
  `src/styles/globals.css`.

### Security-Header

**Zentral in Caddy** (`deploy/hetzner/Caddyfile`) — `(security_headers)`-Snippet
(HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy,
Permissions-Policy) plus per-Subdomain CSP. Begruendung: F-12 (siehe
`docs/security-findings.md`) — eine Quelle, nicht in jeder API-/Web-Antwort
duplizieren. Der lokale `apps/web/nginx.conf` setzt bewusst **keine** Header
(nur SPA-Fallback + Healthcheck). Neue Header → Caddyfile, nicht
`next.config`/`nginx.conf`/Response-Middleware.

### DoD (Frontend-Aenderung)

`npm run lint`, `npx tsc --noEmit`, `npm run test:coverage`, `npm run build` — alle gruen,
lokal verifiziert vor jedem Push. Stack-uebergreifend siehe auch
`docs/CLAUDE-PROFILE.md`.

## Workflow

- Erst verifizieren: nach jeder Aenderung Tests + Lint des betroffenen Stacks
  ausfuehren; bei Bugfixes erst einen reproduzierenden, failing Test.
- Ursache statt Symptom beheben; groessere Aenderungen zuerst als Plan.

## Repository-Etikette

- Branches `feat/<kurz>`, `fix/<kurz>` (Cloud nutzt automatisch `claude/`-Praefix).
- Conventional Commits; PR mit beschreibender Message + Session-Link; 1 Review.

## Security

- Fuer Auth, DB-Zugriff, MCP-Tools und externe Inputs den Subagent
  `security-reviewer` nutzen.
