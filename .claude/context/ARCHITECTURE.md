# ARCHITECTURE — Wie gebaut (Struktur-Karte)

Modularer Monolith (ADR-0001), uv-Workspace im Repo-Root. Details:
[`../../docs/architecture.md`](../../docs/architecture.md) + [`../../docs/adr/`](../../docs/adr/).

## Stack

- **Backend:** Python, FastAPI (REST) + FastMCP (MCP-Server), asyncpg (ADR-0003).
- **Frontend:** React 18 + Vite 7, TypeScript strict, Tailwind v4
  (`@theme inline`, kein config-File), shadcn-Primitives, BlockNote-Insel (ADR-0022).
- **DB:** Supabase/Postgres; Migrationen bei der API; RLS als 2. Verteidigungslinie.
- **Auth:** Supabase Auth (JWT) für Web; eigene API-Token-Tabelle für Agenten.
- **Objekt-Storage:** MinIO/S3 hinter einem Port (ADR-0048) — nur Container, SDK
  Apache-2.0. Optional: ohne Konfiguration läuft alles außer Ingest/Blob-Reads.
- **Tabellen-Store:** SQLite, eine Datei pro WorkArea (ADR-0049).

## Subsysteme (seit WorkArea/KB, ADR-0047/0048/0049)

- **BlobStore-Port** (`apps/api/.../blobstore/`) — hexagonal wie `embeddings/`:
  `put/get/exists/delete/list_keys` auf content-addressed Keys
  `blobs/{workspace_id}/{sha256}`. Adapter MinIO + In-Memory (Tests). Das
  Workspace-Präfix **ist** die Tenancy-Grenze im Storage: GDPR-Export/-Purge
  sind ein Präfix-Listing, kein Join. Bewusst kein Cross-Workspace-Dedup.
  `None` (unkonfiguriert) ist ein gültiger Betriebsmodus, kein Fehler.
- **Tabellen-Store** (`apps/api/.../tablestore/`) — eine SQLite-Datei je
  WorkArea; **die Datei ist die Isolationsgrenze** (Cross-Area-SQL ist physisch
  unmöglich). Read-only ist eine **Engine**-Garantie, keine Konvention:
  `mode=ro` + `query_only` + Authorizer mit Opcode- **und** Funktions-Allowlist,
  dazu Zeit-, Zell- und Result-Budgets. Schema/Katalog leben in Postgres
  (`wa_table`), die Datei trägt nur Daten.
- **Getrennte Suchindizes** — WorkArea-Passagen liegen in `wa_chunk` mit
  eigenem tsvector/GIN; `content_chunk` (Resource-Achse) wird **nicht**
  erweitert. Kuratierte und arbeitende Achse bleiben auch im Retrieval getrennt.
- **Zugriffslog** (`agent_access_log`) — automatisch beim Lesen/Schreiben von
  WorkArea-/KB-Elementen, dedupliziert je (Element, Operation, Kalendertag).
  Hält Sensitivität und Modell-Anbieter/-Name als **Snapshot zum
  Zugriffszeitpunkt** fest (nie rückwirkend umgestuft) und hängt bewusst nicht
  am Agent-CASCADE (`ON DELETE NO ACTION`) — nur der Hard-Purge räumt es ab.
- **Retention-Sweeps** (`core/purge.py`) — der Purge-Cron deckt jetzt drei
  Speicher ab: Postgres (Artifact-Fristen), Objekt-Storage (Blob-Orphans in
  beide Richtungen) und Dateisystem (SQLite-Dateien gelöschter Areas).

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
- **Ports & Adapters** für alles, was außerhalb von Postgres liegt
  (`embeddings/`, `blobstore/`) — der Kern importiert nie einen Adapter,
  nur die `build_*`-Fabrik.
- **Menschen-Vorbehalt:** Area-Grants und die Modell-Konfiguration eines Agenten
  setzen Menschen, keine Agenten — sonst schriebe sich ein Agent seine eigenen
  Rechte bzw. seinen eigenen Compliance-Nachweis.

_Update nur bei Strukturänderung._
