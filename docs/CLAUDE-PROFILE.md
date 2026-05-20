# Who2Be — Projekt-Profil

> Teil F der Resource "Claude Code in der Cloud — Software-Development-Pipeline".
> Fuellt die Leerstellen, die ein generischer Guide nicht kennen kann.
> `TODO`-Stellen ersetzen, sobald die jeweilige Phase steht.

## Repository

- Repo-URL: `https://github.com/luetzey/who2be`
- Hauptsprache / Stack: Python (FastAPI + FastMCP) Backend, React (TypeScript)
  Web-UI, Supabase (Postgres)
- Default-Branch: `main`
- Branch-Konvention: `feat/<kurz>`, `fix/<kurz>` (Cloud nutzt automatisch
  `claude/`-Praefix)
- PR-Konvention: Conventional Commits, Squash-Merge, 1 Review

## Befehle (die Verifikations-Schleife)

- Dependencies: `uv sync` (Python, Root-Workspace) · `npm ci` (in `apps/web/`)
- Tests: `uv run pytest -q` · `npm test`
- Lint: `uv run ruff check .` · `npm run lint`
- Typecheck: `uv run mypy .` · `npx tsc --noEmit`
- Build: `docker compose build` · `npm run build` (in `apps/web/`)

## Cloud-Environment

- Network-Level: Trusted reicht fuer lokale Entwicklung; ab Phase 3 (Hetzner)
  auf Custom umstellen.
- Allowlist-Domains (bei Custom): `TODO: Hetzner-Supabase-Domain eintragen,
  sobald Phase 3 steht (z. B. *.who2be.<deinedomain>)`
- Env-Variablen (nur Namen): `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`,
  `SUPABASE_SERVICE_ROLE_KEY`, `JWT_SECRET` —
  `TODO: bestaetigen, sobald Phase 1 (Auth) steht`
- Pro Session zu startende Services: PostgreSQL (lokal via `docker compose up -d`)

## Definition of Done

- [ ] Alle Tests gruen (pytest + Web)
- [ ] Lint + Typecheck ohne Fehler (ruff/mypy + eslint/tsc)
- [ ] Neuer/angepasster Test deckt die Aenderung ab
- [ ] PR mit beschreibender Message + Session-Link

## Offene Punkte — nur ueber die Web-/Account-Oberflaeche loesbar

Diese Schritte aus Teil A/C der Resource kann ein Cloud-Agent nicht ausfuehren:

- **A1** GitHub App fuer `luetzey/who2be` autorisieren — noetig fuer Auto-fix.
- **A2** Cloud-Environment im Environment-Selector anlegen.
- **A2** Ab Hetzner-Deploy (Phase 3): Network-Level Custom + Domains freigeben.
- **C** Optional: Routine fuer naechtliche Backlog-Pflege oder Review auf
  `pull_request.opened` unter claude.ai/code/routines.
