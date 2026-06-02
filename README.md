# who2be

Selbst-gehostete AgentDB fuer versionierte Persona- und Playbook-Verwaltung —
die zentrale Konfigurationsquelle fuer AI-Agenten.

## Stack

- **API** — FastAPI (`apps/api/`)
- **MCP** — FastMCP-Server (`apps/mcp/`)
- **Web** — React/TypeScript (`apps/web/`)
- **Shared** — Pydantic-Models (`packages/models/`)
- **DB** — Supabase (Postgres); lokal via Docker-Compose, Ziel-Hosting Hetzner

## Entwicklung

Mono-Repo: Python als uv-Workspace im Root, Web unter `apps/web/`.

```bash
docker compose up -d   # lokale Postgres/Supabase
uv sync                # Python-Dependencies
cd apps/web && npm ci  # Web-Dependencies
```

## Claude Code

Repo-Setup fuer Claude Code on the web: siehe `CLAUDE.md`, `.claude/` und
`docs/CLAUDE-PROFILE.md`.

## License

Lizenziert unter der [Functional Source License 1.1 (Apache 2.0 Future)](LICENSE.md)
— frei fuer interne Nutzung, kein konkurrierendes Hosting; jedes Release wird
zwei Jahre nach Veroeffentlichung automatisch Apache-2.0. Fuer eine kommerzielle
Enterprise-Lizenz: <luetzey@gmail.com>.
