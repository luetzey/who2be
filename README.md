# Who2Be

Selbst-gehostete **AgentDB** fuer versionierte Persona- und
Playbook-Verwaltung — die zentrale Konfigurationsquelle fuer AI-Agenten.

Statt System-Prompts, Workflows und Wissensdokumente in Chat-Verlaeufen,
Notizen oder Repos zu verstreuen, verwaltet Who2Be sie als **versionierte,
status-gefuehrte Aggregate** (Draft → Review → Active → Archived) und liefert
sie Agenten zur Laufzeit ueber einen **MCP-Server** aus.

## Features

- **Personae** — Identitaet, Ton, Grenzen und Modi eines Agenten, versioniert
  mit Status-Workflow und Diff-Ansicht
- **Playbooks** — Schritt-Workflows mit Trigger-Keywords, komponierbar zu
  Composite-Buendeln (ADR-0024)
- **Resources** — Wissensdokumente mit Block-Editor (BlockNote), Block-Refs
  und Reverse-Lookups (ADR-0022)
- **Agents** — konkrete Agenten-Konfigurationen mit expandiertem
  System-Prompt, Tool-Policy und kuratiertem Langzeit-Gedaechtnis (ADR-0044)
- **System-Prompt-Templates & Externe Tools** — wiederverwendbare
  Prompt-Bausteine (ADR-0040) und MCP-Tool-Bindings mit `tool-ref`-Platzhaltern
  (ADR-0043)
- **MCP-Server** — Read-, Write-, Search- und Discovery-Tools inkl.
  Feedback-Flywheel (`record_usage`/`submit_feedback`, ADR-0038); Anbindung via
  stdio oder OAuth-2.1-Remote-Connector (ADR-0036), z. B. an Claude Code oder
  Claude.ai
- **Multi-Tenancy & RBAC** — Organisationen → Workspaces,
  Rollen `admin > editor > viewer`, Magic-Link-Invitations, MFA-Step-up
  (ADR-0023)
- **Zwei Editionen aus einer Codebase** — On-Prem (signierter Lizenz-Key) und
  Cloud (Billing-Paket), build-isoliert (ADR-0028/0029)

## Architektur

| Komponente | Pfad | Stack |
|---|---|---|
| REST-API | `apps/api/` | FastAPI, `/v1/workspaces/{ws_id}/...` |
| MCP-Server | `apps/mcp/` | FastMCP (stdio + HTTP/OAuth) |
| Web-UI | `apps/web/` | Vite + React 18 + TypeScript, Tailwind v4, shadcn |
| Geteilte Models | `packages/models/` | Pydantic |
| Cloud-Billing (optional) | `packages/billing/` | Mollie; nur im Cloud-Build |
| Datenbank | — | Supabase (Postgres), lokal via Docker-Compose |
| Deployment | `deploy/hetzner/` | Docker Compose + Caddy (Auto-HTTPS) |

Python laeuft als uv-Workspace im Repo-Root; Architektur-Entscheidungen sind
als ADRs unter [`docs/adr/`](docs/adr/) dokumentiert.

## Quickstart (lokal)

Voraussetzungen: Docker, [uv](https://docs.astral.sh/uv/), Node 22+.

```bash
git clone https://github.com/luetzey/who2be.git && cd who2be
cp .env.example .env       # Env-Vorlage anpassen
docker compose up -d       # lokale Postgres/Supabase
uv sync                    # Python-Dependencies (On-Prem-Kern)
uv run uvicorn who2be_api.main:app --reload   # API auf :8000

cd apps/web && npm ci && npm run dev          # Web-UI auf :5173
```

MCP-Server starten: `uv run python -m who2be_mcp.server` — Anbindung an
Claude Code/Claude.ai siehe [`docs/mcp-claude-code.md`](docs/mcp-claude-code.md).
Cloud-Edition (inkl. Billing): `uv sync --group billing`.

## Dokumentation

- [`docs/adr/`](docs/adr/) — Architecture Decision Records
- [`docs/standards/`](docs/standards/) — Engineering-Standards
  (Architektur, Coding, Testing, Security, Frontend, Compliance)
- [`docs/frontend/design-language.md`](docs/frontend/design-language.md) —
  Designsprache „Warm Citrus"
- [`deploy/hetzner/README.md`](deploy/hetzner/README.md) — Produktions-Deploy
  (Compose, Caddy, Backups, Runbook)
- [`ROADMAP.md`](ROADMAP.md) — was erledigt ist und was kommt

## Entwicklung & Beitraege

Workflow, Konventionen und die Definition of Done (Lint, Typecheck, Tests mit
Coverage-Ratchet, Lizenz-Gates) stehen in [`CONTRIBUTING.md`](CONTRIBUTING.md).
Repo-Setup fuer Claude Code: `CLAUDE.md`, `.claude/` und
`docs/CLAUDE-PROFILE.md`.

Sicherheitsluecken bitte nicht oeffentlich melden — siehe
[`SECURITY.md`](SECURITY.md).

## License

Lizenziert unter der [Functional Source License 1.1 (Apache 2.0 Future)](LICENSE)
— frei fuer interne Nutzung, kein konkurrierendes Hosting; jedes Release wird
zwei Jahre nach Veroeffentlichung automatisch Apache-2.0. Drittanbieter-Lizenzen:
[`THIRD-PARTY-LICENSES.md`](THIRD-PARTY-LICENSES.md). Fuer eine kommerzielle
Enterprise-Lizenz: <luetzey@gmail.com>.
