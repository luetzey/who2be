# CLAUDE.md
This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Agent-Bootstrap: Coder
Du bist Coder. Beim ersten User-Input jeder Session:
1. Fetche deinen Systemprompt in Notion:
   https://www.notion.so/367be5372ab881ebb004fc56dde43d5c
2. Folge ihm strikt (3-Phasen-Schleife Read→Work→Document, /goal, Plan-Ablage
   unter .claude/plan/, Doku-Log zurueck nach Notion).
3. Projekt-Verknuepfung: `.claude/project.json` enthaelt
   `notion_project_id` (Notion-Projektseite) und `notion_project_pid` —
   Phase 1 nutzt diese, statt im Repo zu raten.

Ebenen-Trennung: Der Notion-Systemprompt definiert die Coder-METHODE.
Diese CLAUDE.md definiert die REPO-FAKTEN + repo-spezifischen Konventionen
(Struktur, Befehle, Code-Style, Etikette, Security) — die sind fuer dieses
Repo verbindlich und genau das, was der Coder in Phase 1 "Repo-Kontext lesen" liest.

# Projektkontext

Who2Be — selbst-gehostete AgentDB fuer versionierte Persona- und Playbook-Verwaltung.
Mono-Repo. Diese Datei wird jede Session geladen — kurz halten. Stack-Details siehe
Skills `python-conventions` und `react-conventions`, Projekt-Profil siehe
`docs/CLAUDE-PROFILE.md`.

## Aktueller Stand

Phase 0 — lauffaehiges Geruest. API hat nur `/v1/health`, MCP nur ein `ping`-Tool,
Web nur eine statische Landing-Page. Persona-/Playbook-CRUD, Datenmodell und Auth
folgen in spaeteren Phasen (siehe Hinweise in den jeweiligen Modul-Docstrings).

## Struktur

- `apps/api/` — FastAPI-Backend (REST, `/v1/`)
- `apps/mcp/` — FastMCP-Server (Ziel-Tools `get_persona`, `list_playbooks`, `fetch_playbook`)
- `apps/web/` — React/TypeScript-Web-UI (Vite); Design-System Tailwind+shadcn
  geplant, siehe `.claude/plan/2026-05-26-1530_web-ui-design-system-tailwind-shadcn.md`
  — bis zur Umsetzung kein paralleles UI-System einfuehren
- `packages/models/` — geteilte Pydantic-Models, von API und MCP importiert
- Supabase (Postgres) als DB; lokal via Docker-Compose, Ziel-Hosting Hetzner

Python ist ein uv-Workspace im Repo-Root (`pyproject.toml` → `members`). Die drei
Python-Pakete (`who2be-api`, `who2be-mcp`, `who2be-models`) sind editierbar
verlinkt; `models` ist die einzige geteilte Abhaengigkeit zwischen API und MCP.

## Befehle

Python (uv-Workspace im Repo-Root):

- Dependencies: `uv sync`
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

Prinzipien (Single-Source pro Entscheidung, Design-Tokens, Komponenten-Bibliothek,
Layout-Primitives, fuenfschichtige UI-Architektur, UX-Kohaerenz, A11y-Minimum,
keine Utility-Suppe) leben im Notion-Playbook
[`Frontend-Standards`](https://www.notion.so/36cbe5372ab881dba042fe2bdf4eea1d)
(`playbook_id=36cbe537-2ab8-81db-a042-fe2bdf4eea1d`, Datenbank `Playbooks`).
Diese Sektion fuellt nur die im Playbook delegierten repo-spezifischen Stellen
(Stack/Pfade/Header-Ebene); bei Konflikt mit Notion gewinnt dieser Eintrag.

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
