# Projektkontext

Who2Be — selbst-gehostete AgentDB fuer versionierte Persona- und Playbook-Verwaltung.
Mono-Repo. Diese Datei wird jede Session geladen — kurz halten. Stack-Details siehe
Skills `python-conventions` und `react-conventions`, Projekt-Profil siehe
`docs/CLAUDE-PROFILE.md`.

## Struktur

- `apps/api/` — FastAPI-Backend (REST, `/v1/`)
- `apps/mcp/` — FastMCP-Server (`get_persona`, `list_playbooks`, `fetch_playbook`)
- `apps/web/` — React/TypeScript-Web-UI
- `packages/models/` — geteilte Pydantic-Models, von API und MCP importiert
- Supabase (Postgres) als DB; lokal via Docker-Compose, Ziel-Hosting Hetzner

## Befehle

Python (uv-Workspace im Repo-Root):

- Dependencies: `uv sync`
- Tests: `uv run pytest -q`
- Lint: `uv run ruff check .`
- Format: `uv run ruff format .`
- Typecheck: `uv run mypy .`

Web (in `apps/web/`):

- Dependencies: `npm ci`
- Tests: `npm test`
- Lint: `npm run lint`
- Typecheck: `npx tsc --noEmit`
- Build: `npm run build`

Lokale Infrastruktur: `docker compose up -d` (Postgres/Supabase).

## Code-Style (nur Abweichungen)

- Python: Type Hints Pflicht; Pydantic an API-/MCP-Grenzen; kein blankes `except:`.
- TypeScript: strikt, kein `any` ohne Begruendung; funktionale Komponenten + Hooks;
  bestehende Patterns wiederverwenden.

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
