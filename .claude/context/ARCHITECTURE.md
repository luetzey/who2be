# ARCHITECTURE — Wie gebaut (Struktur-Karte)

Modularer Monolith (ADR-0001), uv-Workspace im Repo-Root. Details:
[`../../docs/architecture.md`](../../docs/architecture.md) + [`../../docs/adr/`](../../docs/adr/).

## Stack

- **Backend:** Python, FastAPI (REST) + FastMCP (MCP-Server), asyncpg (ADR-0003).
- **Frontend:** React 18 + Vite 7, TypeScript strict, Tailwind v4
  (`@theme inline`, kein config-File), shadcn-Primitives, BlockNote-Insel (ADR-0022).
- **DB:** Supabase/Postgres; Migrationen bei der API; RLS als 2. Verteidigungslinie.
- **Auth:** Supabase Auth (JWT) für Web; eigene API-Token-Tabelle für Agenten.

## Modul-Map (Modul → Verantwortung)

- `apps/api/` — REST, hart auf `/v1/workspaces/{ws_id}/...`; Schichten
  **Router → Service → Repository** (ADR-0002).
- `apps/mcp/` — FastMCP Read- + Write-Tools, workspace-aware, Reads filtern auf
  `status='active'` (ADR-0030).
- `apps/web/` — React-UI; Feature-Ordnerbaum `features/<domain>/{pages,components}`.
- `packages/models/` — geteilte Pydantic-Models (API + MCP importieren, nie
  duplizieren).
- `packages/billing/` — optionales Cloud-Billing, build-zeit-isoliert (ADR-0029);
  Kern hängt nie statisch davon ab.

## Boundaries & Patterns

- **Abhängigkeitsrichtung:** Router → Service → Repository; Geschäftslogik in
  Services, Tools/Router dünn.
- **Repository-Pattern** + generische `VersionedAggregateRepository` für
  Persona/Resource/Playbook (versionierter Kern).
- **Versionierung** über History-Tabellen + `VersionStatus`-Invariante
  (partial-unique-index) (ADR-0004/0020).
- **Entitlements:** `org_entitlement` ist die einzige gelesene SSoT (ADR-0028).
- **Security-Header** zentral in Caddy (eine Ebene), nicht je Response.

_Update nur bei Strukturänderung._
