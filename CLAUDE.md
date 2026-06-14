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

Phase 3 ist abgeschlossen (Stand 2026-05-29). Master-Plan:
`.claude/plan/2026-05-29-1900_phase-3-ux-polish.md` — alle Sub-Pläne geflippt.

**Phase 3 — UX-Polish nach Live-Smoke:**

- **3-0 Sync:** Migration `0017` (Status-Default `draft` für neue Versions),
  Migration `0018` (Playbook-Type-CHECK-Enum), Models `PersonaContent` +
  `PlaybookType` + `PlaybookUsage`/`ResourceUsage`. ADR-0020 um Default-Draft
  ergänzt.
- **3-A Backend:** Repo-Inserts setzen `status='draft'` explizit;
  Section-aware Block-Refs (Heading-Anker + Section-Slice serverseitig);
  Reverse-Lookups `GET /playbooks/{id}/usages` und `/resources/{id}/usages`;
  Tags-DISTINCT-Endpoint `GET /playbooks/tags`.
- **3-B Frontend Editor/Forms:** BlockNote-CSS-Scope-Fix (Slash-Menü mit
  Hintergrund, Heading-Sizes), Persona-`properties` → BlockNote-Profil +
  TagInput, Playbook-Type-Select + Multi-Select-TagInput, BlockNote-Body.
- **3-C Frontend Navigation/UX:** `WorkspaceSwitcher` in der AppShell,
  Status-Action-Bar auf jeder Detail-Page sichtbar (auch bei `inactive` →
  „Reaktivieren als Draft"), Backlinks-Anzeige in Playbook- und
  Resource-Detail.
- **3-D Invitation Onboarding:** GoTrue-Magic-Link mit `redirect_to=…/accept?via=magic`,
  Email-Mismatch-Guard auf der Accept-Route, Login-Page `next`-Param gegen
  Open-Redirects gehärtet.

**Phase 2 — Vollwertige App** (Stand 2026-05-29):

- **2.1a — Tenancy:** `User → org_member → Organization → Workspace → Entity`;
  API hart auf `/v1/workspaces/{ws_id}/...`; API-Tokens pro Workspace gepinnt.
- **2.1b — Status + Dashboard:** `VersionStatus {draft, review, active, inactive}`
  pro Version, DB-Invariante via partial-unique-index; `POST .../versions/{v}/transition`;
  PUT auf Active erzeugt Draft (409 bei vorhandenem Draft); MCP-Reads filtern auf
  `status='active'`; Dashboard-Endpoint + -Page (KPIs + Activity + Status-Distribution).
- **2.2 — Resources + BlockNote:** Resource-Aggregat versioniert wie Persona/Playbook;
  Playbook→Resource-Block-Refs via `block_id`; MCP `list_resources` / `fetch_resource`;
  Web-Editor isolierte BlockNote-Insel (ADR-0022).
- **2.3 — Multi-User RBAC:** Rollen `admin > editor > viewer` via `workspace_member`;
  `require_role`-Gate auf Mutating-Endpoints; Token-Snapshot-Rolle (ADR-0023);
  Invitations + GoTrue-Mail (single-use, sha256-Hash); Members-Page + Accept-Flow.

**Agenten-Achsen (Track D/E, 2026-05-31):** Composite-Playbooks (ADR-0024),
  Applied-via-Pill, Persona-Modi + `profile`-Target, Resource-Tags —
  vollstaendige Agenten-Reise-Doku in `docs/agent-axes.md`. Plan:
  `.claude/plan/2026-05-31-1630_composite-applied-modi.md`.

**MCP-Write-Tools (ADR-0030, 2026-06-05):** Der MCP-Server exponiert
  Mutations-Tools fuer alle vier Kernelemente (Persona, Playbook, Resource,
  Agent): create/update/transition/restore + Verknuepfungs-Setter. Duenner
  Adapter — Autorisierung (editor; jeder Uebergang ab/zu `active` —
  Promote/Retire/Reset — admin), Owner-Scoping und
  der Draft→active-Workflow bleiben serverseitig. Kein delete ueber MCP.
  Loest ADR-0012 (deferred) ab.

**Einzel-Element Delete + Export (ADR-0032, 2026-06-05):** Hard-Delete fuer
  Persona/Playbook/Resource (`DELETE …/{entity}/{id}`, `editor`-Gate, FK-Cascade
  raeumt Versionen + ausgehende Links). Eingehende Referenzen blockieren mit
  **409** + `DeleteBlocked`-Body (`message` + `blocked_by`-Map: Persona←Agenten,
  Playbook←Personas/Composites, Resource←Playbooks/Composites) — kein Cascade auf
  fremde Aggregate. Einzel-Export `GET …/{entity}/{id}/export?format=json|markdown`
  (Viewer-offen; JSON = Identitaet + alle Versionen, Markdown = gerenderter Body
  der aktiven Version + YAML-Frontmatter). Bewusst **kein** MCP-Delete/-Export
  (ADR-0030 bleibt). Plan: `.claude/plan/2026-06-05-1500_single-element-delete-export.md`.

Nächste Blöcke offen (kein aktiver Plan): Security-Quick-Wins
(`docs/security-findings-phase-2.md` §TODO 1–3), CSP/Header-Pass (F-12),
Public-Switch + FSL-Lizenz (`…1935_license-fsl-setup`,
`…2028_public-switch-github-repo`),
Enterprise-License-Hooks (`…0528_enterprise-license-management`).

## Struktur

- `apps/api/` — FastAPI-Backend (REST, `/v1/workspaces/{ws_id}/...`)
- `apps/mcp/` — FastMCP-Server. Read-Tools (`get_persona`, `list_playbooks`,
  `fetch_playbook`, `list_resources`, `fetch_resource`, `fetch_agent`,
  `list_triggers` — workspace-aware, filtern auf `status='active'`) plus
  Write-Tools (ADR-0030: create/update/transition/restore + Link-Setter fuer
  Persona/Playbook/Resource/Agent; Autorisierung serverseitig)
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
- Tests: `uv run pytest -q`
- Einzeltest: `uv run pytest apps/api/tests/test_health.py::test_health`
- Lint: `uv run ruff check .`
- Format: `uv run ruff format .`
- Typecheck: `uv run mypy .`
- API starten: `uv run uvicorn who2be_api.main:app --reload`
- MCP starten: `uv run python -m who2be_mcp.server`

Web (in `apps/web/`):

- Dependencies: `npm ci`
- Dev-Server: `npm run dev`
- Tests: `npm test` (Vitest); Einzeldatei: `npm test -- src/App.test.tsx`
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

`npm run lint`, `npx tsc --noEmit`, `npm test`, `npm run build` — alle gruen,
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
