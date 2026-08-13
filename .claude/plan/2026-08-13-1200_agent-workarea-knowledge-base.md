# Plan: Agent WorkArea + Knowledge Base (MVP, Phasen 1+2)

**Datum:** 2026-08-13 · **Branch:** `claude/agent-workarea-kb-plan-755yaw` · **Status:** in Umsetzung

**Spec:** MVP-Spezifikation „Agent WorkArea + Knowledge Base" (2026-08-10, User-Vorlage) ·
**ADRs:** 0047 (Umbrella) · 0048 (Blob-Storage) · 0049 (Tabellen-Store)

## Context

Agenten haben in Who2Be keinen Arbeitsort: Das Resource-Aggregat (draft/review/active,
409 bei bestehendem Draft) ist für kuratiertes Wissen richtig, für hochfrequentes
Agenten-Schreiben aber ein Dauerkonflikt. Zudem fehlt eine verknüpfte, belegpflichtige
Wissensschicht. Dieses Vorhaben führt zwei neue, **unversionierte** Subsysteme ein —
**WorkArea** (Rohmaterial: docs/tables/blobs, lockfrei bzw. optimistisch) und
**Knowledge Base** (kuratiert: getypte Kanten mit serverseitiger Belegpflicht) — mit genau
einem expliziten Übergang (`promote_artifact` → Resource-Draft) und **null Änderung am
Resource-Aggregat**. Rahmung gegen PROJECT.md-Non-Goals: WorkArea/KB sind
*Kontext-Speicher für Agenten* (kein CMS/Wiki, kein Runtime-Host) — PROJECT.md wird im
Doku-WP entsprechend ergänzt.

Außerhalb dieses Plans: Spec-P1 (TTL/Verfall H, Challenger I, Drift J) und P2 (UI,
Graph-Viz, semantische Suche). Die P1-Schemafelder (`ttl_expires_at`, `status live|stale`,
`derivation_depth`, Conflict-Tabelle) werden aber JETZT angelegt (Conflict brauchen L und
D/O bereits).

## User-Entscheidungen (2026-08-13, bindend)

1. **Scope:** Phase 1 (A–E) und Phase 2 (F–G, K–N, O) gleich detailliert in einem Plan.
2. **Verortung:** bestehender Stack — apps/api + apps/mcp + packages/models,
   Workspace-Tenancy, dieselbe Postgres-DB.
3. **Blob-Storage:** MinIO/S3-kompatibel, content-addressed (SHA-256), neuer Compose-Dienst.
4. **Kontodaten:** Ausgaben-Analyst läuft gegen Cloud-API — mit Lauf-Protokoll; Konto-Ingest
   bleibt in Phase 2.
5. **Private Areas:** Menschen ab Rolle `editor` lesen alles (auch private Agent-Areas);
   „privat" heißt privat gegenüber anderen **Agenten**. Viewer sehen nur shared Areas.
6. **Lauf-Protokoll (F):** **Auto-Zugriffslog + Modell-Config am Agenten** — Server loggt
   jeden Agent-Zugriff automatisch (append-only, dedupliziert pro Element+Tag);
   `model_provider`/`model_name` sind betreiber-gepflegte, auditierte Felder am Agenten.
   Kein `record_run`-Selbstauskunfts-Tool.
7. **Auswertung (M):** **Kein serverseitiges Chart-Rendering.** Who2Be unterstützt schnelle,
   agentengerechte Datenabfrage: `query_table` mit Format-Wahl + `save_query_result`
   (Server persistiert Query + eingefrorenes Ergebnis als doc-Artifact — Zahlen schreibt
   der Server, nie das Modell; Spec §10.6 bleibt Server-Garantie).

## Verifizierter Ist-Stand (Kurzfassung)

- Fehler-Taxonomie: `ApiGateError` in `apps/api/src/who2be_api/core/errors.py`; Titel-Registry
  `_PROBLEM_TITLES` + `_WORKSPACE_PREFIX = "/v1/workspaces/{workspace_id}"` in `main.py:119–133`;
  `ProblemReason`-Literal in `packages/models/src/who2be_models/errors.py:23`. Guardrail ARC-3:
  keine neuen HTTPException/SQL in `apps/api/**/services/`.
- Migrations: Plain-SQL, letzte ist `0072_agent_memory_vector.sql` → **nächste 0073**.
  Vorlagen: `0066_agent_memory.sql` (agent-scoped, generated tsvector),
  `0070_content_chunk.sql` (Chunk-Tabelle, GIN, RLS `tenant_isolation`, pg_roles-Guard).
- Capabilities: `AgentToolPolicy`/`AgentCapability` in
  `packages/models/src/who2be_models/tool_policy.py`; Anti-Eskalation `is_within.bool_fields`
  (`:280–291`) **muss** erweitert werden; `agent.tool_policy` ist jsonb
  (`0046_agent_tool_policy_and_token_agent.sql:27`) → neue Capabilities ohne Migration.
  Gates `require_role`/`require_capability`/`require_write_rate` in `core/security.py:241/276/389`.
- Read-Scoping: `core/agent_scope.py` (restrict_ids-Muster); `readable_content_scope()` (`:265`)
  ist auf die 5 Kern-Typen verdrahtet → WorkArea/KB bekommen eigenen Helper.
- MCP: 58 Tools in `apps/mcp/src/who2be_mcp/server.py` (1634 LOC, ADR-0005: reiner
  HTTP-Client); Pflicht `@mcp.tool(output_schema=None)` (Payload-Budget, `server.py:104`) +
  `@with_tool_log`; SSoT `packages/models/src/who2be_models/tool_requirements.py`
  (`ReadDomain`-Literal `:46`, Count-Guard `packages/models/tests/test_tool_requirements.py:240`,
  Paritätstests `apps/mcp/tests/test_policy_filter.py:192/:252`); zusätzlich
  `services/placeholders/resolvers/tools.py::_TOOLS` pflegen.
- Suche-Vorlage: `services/content_chunks.py` (Heading-Split, ADR-0021-Anker
  `<entity_id>#<block_id>`, 4000-Zeichen-Cap) + `repositories/content_chunk_repository.py`
  (Scope-CTE VOR Ranking, RRF).
- Promote-Pfad: bestehender `ResourceService.create` (`services/resource_service.py:143`,
  Gates editor + `resource_write` + Quota + Slug + Locale → 201 Draft v1);
  Provenance via `status_history`-Note (append-only).
- Infra: KEIN Object-Storage/Upload/Scheduler im Repo. Port-Vorlage
  `apps/api/src/who2be_api/embeddings/{port,service,adapters}`; Nightly = Console-Script +
  Host-Cron (`core/purge.py`, `[project.scripts]`); Compose-One-Shot-Muster
  `set-app-role-password`; Caddy = einzige Header-/CSP-Ebene.
- Lizenz-Gate ADR-0033 (fail-closed): **PyMuPDF (AGPL) und html2text (GPL) verboten**;
  ok: pypdf (BSD-3), beautifulsoup4 (MIT), minio (Apache-2.0).
- ADRs: letzte 0046 → **neu 0047–0049**. Plan-Format-Vorbild:
  `.claude/plan/2026-07-24-1900_sprache-vertiefen-ein-element-eine-sprache.md`.
- Tests: Root-conftest (`migrated_db`, `patched_jwt_secret`, `make_auth_headers`), Seeds
  `who2be_api/testing/workspace_setup.py`, Coverage-Gate `--cov-fail-under=85` (Ratchet);
  MCP-Tests DB-los (httpx.MockTransport + monkeypatch `build_client`).

## Architektur-Entscheidungen (Drei-Optionen-Regel; Details in ADR-0047/0048/0049)

1. **Tabellen-Store = SQLite, eine Datei pro Area** (`WHO2BE_TABLESTORE_DIR`/
   `{workspace_id}/{area_id}.sqlite`; stdlib `sqlite3` via `asyncio.to_thread`, WAL,
   per-Area-`asyncio.Lock`). Read-only-Enforcement als **Engine-Garantie**:
   `PRAGMA query_only=ON` + `Connection.set_authorizer` (Deny außer
   SELECT/READ/FUNCTION) → DROP/UPDATE scheitern in der Engine, Mapping auf 403.
   Katalog (Schema-JSON, dedupe_columns, Kategorien-Spalte) liegt in Postgres (`wa_table`);
   die SQLite-Datei trägt nur Daten. `occurred_at`+`occurred_precision` sind Pflichtspalten
   jeder Tabelle (N); `_dedupe_hash` UNIQUE + `INSERT OR IGNORE` = idempotenter Import (K).
   *Verworfen:* DuckDB (OLAP-Gewicht ohne Nutzen bei 10k Zeilen, kein Authorizer-Äquivalent),
   Postgres-Schema-pro-Area (Isolationslücke ohne SQL-Parser, dynamisches DDL bricht
   Migrations-Disziplin, Spec-Abweichung).
2. **MCP-Split hybrid:** Bestand bleibt in `server.py`; neue Domains als
   Registrierungs-Module `apps/mcp/src/who2be_mcp/tools/{workarea,kb,tables}.py` mit
   `register(mcp)`, Client-Methoden in `clients/{workarea,kb,tables}.py`. Voraussetzung für
   datei-disjunkte parallele WPs. Neuer Drift-Guard
   `apps/mcp/tests/test_tool_payload_budget.py`: tools/list-JSON-Bytes gegen fixes Budget
   (Baseline messen, ×1,45), Docstring-Cap ≤ 1100 Zeichen/Tool.
   *Verworfen:* alles in server.py (Wellen-Konflikt), Voll-Refactoring des Bestands (Risiko
   ohne Feature-Nutzen).
3. **Doc-Format: Block-Liste mit Markdown-Inhalt.** Speicher: `wa_artifact.content` =
   JSONB-Liste `[{block_id (8-stellig, serverseitig vergeben), kind heading|paragraph|code|list,
   level?, md}]`. API/MCP nimmt **Markdown** an, Server splittet deterministisch; `read`
   liefert Markdown mit Anker-Annotation. Anker-Sprache = ADR-0021
   (`<artifact_id>#<block_id>`) → Suchtreffer sind direkt `read(id, anchor)`-fähig.
   `append` = atomares `content || $blocks, rev+1` (lockfrei); `patch` =
   `WHERE rev = $expected_rev`, 0 Zeilen → 409 `rev_conflict` (aktuelle rev im detail).
   Promote nutzt kleinen deterministischen Block→BlockNote-Konverter.
   *Verworfen:* volles BlockNote-JSON als Autorenformat (agent-feindlich, Payload),
   purer Markdown-Text (Anker-Stabilität über Edits prinzipiell ungelöst).
4. **BlobStore: minio-SDK als Kern-Dependency hinter Port**
   (`apps/api/src/who2be_api/blobstore/{port,service,adapters/minio,adapters/memory}`,
   embeddings-Vorbild; Port für Testbarkeit/Austauschbarkeit, nicht Optionalität).
   Objekt-Key `blobs/{workspace_id}/{sha256}` — Workspace-Präfix macht GDPR-Purge/-Export
   trivial (bewusst KEIN Cross-Workspace-Dedup). Ohne Konfiguration: nur Ingest/Blob-Reads
   liefern 503 `blobstore_unconfigured`, Rest läuft voll. Compose: Dienst `minio` (AGPL nur
   als Container wie Postgres — ins ADR) + One-Shot `minio-bootstrap` (Bucket). Env:
   `WHO2BE_BLOBSTORE_{ENDPOINT,ACCESS_KEY,SECRET_KEY,BUCKET,SECURE}`.
   *Verworfen:* optionale Dep-Gruppe (fragmentiert Kern-Feature), separates Paket
   (billing-Muster ist Lizenzgrenze, kein Editions-Bezug hier).
5. **Area-Grants + KB-Sichtbarkeit materialisiert:**
   `work_area_grant(area_id, agent_id, level read|write)`; private Area wird bei erstem
   Zugriff auto-angelegt inkl. materialisierter Owner-Grant-Row (uniforme Filter-SQL).
   KB: `kb_node_source_area` wird bei `create_node` aus content_ref/source_ref aufgelöst und
   bei `derived_from`-Kanten monoton ge-UNION-t (Parent-Menge ist schon transitiv; Kanten im
   MVP nicht löschbar → nie Re-Berechnung). Lesbarkeit: Agent muss ALLE Quell-Areas lesen
   dürfen (NOT-EXISTS-Join **in der SQL-WHERE**, nie Post-Processing); leere Schnittmenge →
   nur Menschen. Neuer Helper `core/workarea_scope.py`
   (`readable_area_ids`/`writable_area_ids`/`ensure_area_access` → 403 `area_forbidden`).
   Menschen: editor+ unrestricted, viewer nur shared. whoami: neues Feld
   `work_areas: [{id, name, scope, level}]`.
   *Verworfen:* rekursive CTE zur Lesezeit (Kosten am heißesten Pfad), Agent-ID-Snapshot am
   Node (materialisiert mutable Grants statt stabiler Areas).
6. **Lauf-Protokoll = Auto-Zugriffslog + Modell am Agenten** (User-Entscheidung 6):
   `agent_access_log` append-only, geschrieben in den Read-/Write-Services für
   agent-gebundene Tokens, dedupliziert per
   `UNIQUE (agent_id, ref_kind, ref_id, access_date)` + `ON CONFLICT DO NOTHING`;
   `sensitivity_at_access` snapshottet der Server. `agent.model_provider`/`model_name`
   (nullable text) pflegt der Mensch über den bestehenden Agent-Update-Pfad; Änderung
   schreibt `audit_log`. Betreiber-Query („welche Elemente gingen je an externen Anbieter")
   wird in `docs/compliance/` dokumentiert. Grenze (ins ADR): Modell gilt pro
   Agent-Konfiguration, nicht pro Einzelaufruf.
   *Verworfen:* record_run-Selbstauskunft (Vollständigkeit = Agenten-Disziplin),
   Session-Lauf-Kontext im MCP (Zustand bricht ADR-0005).

## Datenmodell → Migrations 0073–0079

Alle Tabellen: `workspace_id NOT NULL` + RLS `tenant_isolation` (`app.current_tenant`) +
idempotente GRANTs mit pg_roles-Guard (Muster 0066/0070); FKs `ON DELETE CASCADE` im Subsystem.

- **0073_work_area.sql:** `work_area(id, workspace_id, scope private|shared,
  owner_agent_id NULL→agent CASCADE, name, retention_days NULL, created_at/updated_at,
  CHECK ((scope='private')=(owner_agent_id IS NOT NULL)))`;
  `UNIQUE (workspace_id, owner_agent_id) WHERE scope='private'` (genau eine private Area);
  `UNIQUE (workspace_id, name) WHERE scope='shared'`.
  `work_area_grant(workspace_id, area_id→work_area CASCADE, agent_id→agent CASCADE,
  level read|write, PK (area_id, agent_id))` + Index auf agent_id.
- **0074_wa_artifact.sql:** `wa_artifact(id, workspace_id, area_id→work_area CASCADE,
  type doc|table|blob, title, rev int DEFAULT 1, occurred_at NOT NULL,
  occurred_precision day|minute|unknown, content jsonb NULL (doc-Blockliste),
  content_ref text NULL (blob: sha256 · table: wa_table.id), blob_sha256 NULL
  (Ingest-Provenance), sensitivity general|sensitive DEFAULT general,
  source_system/source_url/fetched_at NULL, created_at/updated_at, updated_by)`;
  Timeline-Index `(workspace_id, occurred_at) WHERE occurred_precision <> 'unknown'`.
  Kein Server-Fallback von occurred_at auf now() — Pflicht-Input (Ausweg: precision=unknown).
- **0075_wa_blob.sql:** `wa_blob(workspace_id, sha256, size_bytes, media_type, storage_key,
  source_url NULL, fetched_at NULL, created_at, PK (workspace_id, sha256))`.
- **0076_wa_chunk.sql:** nach 0070-Vorlage: `wa_chunk(id, workspace_id,
  artifact_id→wa_artifact CASCADE, area_id, block_id, heading_path, ord, text, locale,
  search tsvector GENERATED (german/english/simple nach locale))` + GIN + `(workspace_id,
  area_id)`. **`content_chunk` wird NICHT erweitert** (getrennte Indizes, Spec §10.1).
- **0077_kb.sql:**
  `kb_node(id, workspace_id, tier verified|derived|hypothesis, content text (die Aussage),
  content_ref NULL (Herkunfts-Anker), source_ref NOT NULL
  (sha256:<h> | url:<u> | artifact:<uuid>[#block]), source_ref_kind blob|url|artifact,
  ttl_expires_at NULL, status live|stale DEFAULT live, derivation_depth DEFAULT 0,
  sensitivity, occurred_at, occurred_precision, created_by, created_at/updated_at,
  search tsvector GENERATED ('simple', content))` + GIN + Timeline-Index.
  `kb_edge(id, workspace_id, type supports|contradicts|supersedes|derived_from|belongs_to|
  co_occurs_with, from_anchor, to_anchor, from_node_id/to_node_id NULL→kb_node CASCADE,
  co_query/co_n/co_from/co_to NULL, created_by, created_at,
  CHECK (type<>'co_occurs_with' OR alle co_-Felder NOT NULL), CHECK (co_n IS NULL OR co_n>=20))`
  — der Service liefert das 422 mit tatsächlichem n, die DB ist Backstop.
  `kb_edge_evidence(id, workspace_id, edge_id→kb_edge CASCADE, side from|to, anchor)` —
  „min. 1 pro Seite" prüft der Service in derselben Transaktion (kein Teilzustand).
  `kb_node_source_area(workspace_id, node_id→kb_node CASCADE, area_id→work_area CASCADE,
  PK (node_id, area_id))`.
  `kb_conflict(id, workspace_id, kind node|rule, a_id, b_id, reason, opened_at,
  resolved_at NULL, resolution NULL)`.
- **0078_wa_table.sql:** `wa_table(id, workspace_id, area_id→work_area CASCADE, name,
  schema_json (Spalten/Typen-Allowlist text|integer|numeric|date|timestamp|boolean,
  dedupe_columns, match_column, category_column), created_at/updated_at,
  UNIQUE (area_id, name))`;
  `wa_category_rule(id, workspace_id, area_id CASCADE, pattern, category,
  created_by text ('agent:<id>'|'user:<id>'|'model:<id>'), confidence NULL,
  active DEFAULT true, created_at/updated_at, UNIQUE (area_id, pattern))`;
  `wa_source_convention(id, workspace_id, area_id CASCADE, source_name, convention jsonb
  (Einheiten, Notation, Dezimal-/Datumsformat), created_by, created_at/updated_at,
  UNIQUE (area_id, source_name))`.
- **0079_agent_access_log.sql:** `agent_access_log(id, workspace_id, agent_id→agent CASCADE,
  ref_kind artifact|node|table|blob, ref_id text, operation read|write,
  sensitivity_at_access general|sensitive, access_date date NOT NULL, first_at timestamptz,
  UNIQUE (agent_id, ref_kind, ref_id, operation, access_date))` — GRANT nur SELECT/INSERT
  (append-only); Insert `ON CONFLICT DO NOTHING`.
  Plus: `ALTER TABLE agent ADD COLUMN model_provider text NULL, ADD COLUMN model_name text NULL`.
- **Keine Migration für Capabilities** (`agent.tool_policy` ist jsonb; neue Bool-Felder
  defaulten in Pydantic auf False).

## API (Router → Service → Repo, ARC-3-konform)

Alle Router unter `_WORKSPACE_PREFIX`; jede Mutation `@limiter.limit(write_limit)`, jeder
Agent-Read `Depends(enforce_mcp_read_limit)` (Muster `routers/resources.py:73/98`).

**Neue ProblemReasons** (`who2be_models/errors.py` + `_PROBLEM_TITLES` in `main.py`,
komplett in WP1): `rev_conflict` 409 · `evidence_missing` 422 · `anchor_unresolvable` 422 ·
`tier_upgrade_forbidden` 422 · `correlation_underpowered` 422 (detail: tatsächliches n) ·
`area_forbidden` 403 (nur Write auf lesbare Area; fehlender Read-Grant → 404 `not_found`,
kein Existenz-Leak) · `query_not_readonly` 403 · `convention_missing` 422 ·
`rule_required` 422 · `ingest_unsupported` 422 · `ingest_too_large` 413 ·
`url_forbidden` 403 · `blobstore_unconfigured` 503.

| Router (neu) | Endpunkte (Auswahl) | Gates (im Service) |
|---|---|---|
| `work_areas.py` | POST/GET `/work-areas`, PUT/DELETE `/work-areas/{id}/grants/{agent_id}` | Grants + shared-Anlage: `require_role(editor)`, Grant-Vergabe nur Mensch |
| `wa_artifacts.py` | POST `/work-areas/{area_id}/artifacts`, POST `/wa-artifacts/{id}/append`, PATCH `/wa-artifacts/{id}` (anchor, op, expected_rev), GET `/wa-artifacts/{id}?anchor=`, GET-List, DELETE, POST `/wa-artifacts/{id}/promote` | Writes: `require_capability(workarea_write)` + `ensure_area_access(write)` + `require_write_rate`; Promote delegiert an `ResourceService.create` + `status_history`-Note „Promotet aus wa_artifact <id>, <ts>" |
| `wa_ingest.py` | POST `/work-areas/{area_id}/ingest` (multipart file ODER {url}) | workarea_write + Area-write + Rate |
| `wa_search.py` | GET `/workarea-search?q=&area_id=` | Scope-CTE aus `workarea_scope.readable_area_ids` |
| `kb.py` | POST/PATCH/GET `/kb/nodes`, POST `/kb/edges`, GET `/kb/neighbors?anchor=&type=&depth=1`, GET `/kb-search?q=` | Nodes: `kb_write`; Edges: `kb_edge_write`; Belegpflicht + Anker-Auflösung + Tier-Regeln + O-Validierung in EINER Transaktion |
| `wa_tables.py` | POST `/work-areas/{area_id}/tables`, POST `/wa-tables/{id}/rows`, POST `/wa-tables/{id}/query` (format json\|markdown\|csv, Row-Cap), GET `/wa-tables/{id}` (describe), POST `/wa-tables/{id}/save-result`, PUT `…/conventions/{source}`, POST/GET/PATCH `…/category-rules` | workarea_write + Area-write; `query`: Area-read genügt, Authorizer erzwingt read-only |
| `wa_timeline.py` | GET `/timeline?from=&to=&sources=&granularity=` | read-Grants auf alle sources, sonst 403 |
| erweitert `whoami.py` | Feld `work_areas` | — |

Zugriffslog-Schreibpunkte (nur agent-gebundene Tokens): read/list/search auf
Artifacts/Nodes, `query_table`/`describe`, Blob-Reads; Writes analog mit operation=write.

## MCP-Tools (23 neu → 81 gesamt)

Module `apps/mcp/src/who2be_mcp/tools/{workarea,kb,tables}.py` (+ `clients/…`), jedes Tool
`@mcp.tool(output_schema=None)` + `@with_tool_log` + deutscher Docstring ≤ 1100 Zeichen;
je Eintrag in `MCP_TOOL_REQUIREMENTS` + `resolvers/tools.py::_TOOLS`. `ReadDomain` +=
`"workarea"`, `"kb"`; Timeline läuft unter `read_domain="workarea"` (KB-Anteile serverseitig
per Grant gefiltert).

WorkArea (workarea_write bzw. read: workarea): 1 `create_artifact(title, content_md,
occurred_at, occurred_precision='minute', area_id=None→privat, sensitivity='general',
source_system=None, source_url=None)` · 2 `append_artifact(id, content_md)` ·
3 `patch_artifact(id, anchor, op replace|insert_after|delete, content_md, expected_rev)` ·
4 `read_artifact(id, anchor=None)` · 5 `list_artifacts(area_id=None)` (Docstring: „NICHT der
Einstieg — nutze search_workarea", Anforderung C) · 6 `delete_artifact(id)` ·
7 `ingest(area_id=None, url=None, file_b64=None, filename=None, occurred_at=None,
sensitivity=None)` · 8 `search_workarea(query, area_id=None)`.

KB (kb_write / kb_edge_write / read: kb): 9 `search_kb(query)` (**zwei Such-Tools statt
`search(scope)`** — „nie beide" strukturell erzwungen) · 10 `create_node(content, tier,
source_ref, occurred_at, occurred_precision='day', content_ref=None, sensitivity='general')` ·
11 `update_node(id, content=None, tier=None, additional_source_ref=None)` ·
12 `create_edge(from_anchor, to_anchor, type, evidence_from[], evidence_to[], co_query=None,
co_n=None, co_from=None, co_to=None)` · 13 `neighbors(anchor, type=None, depth=1)`
(co_occurs_with immer mit Fallzahl, O) · 14 `promote_artifact(artifact_id,
target_resource_id=None)` (requirement: resource_write, bestehend).

Tables/Timeline (workarea_write bzw. read: workarea): 15 `create_table(area_id, name, schema)`
(occurred_at-Spalte Pflicht) · 16 `insert_rows(table_id, rows[], source_artifact_id=None,
source_name=None, new_rules=[])` · 17 `query_table(table_id, sql, format='json')` ·
18 `describe_table(table_id)` (Schema, Zeilenzahl, Wertebereiche, Konventionen) ·
19 `timeline(from_, to, sources[], granularity day|week|month)` · 20 `set_convention(area_id,
source_name, convention)` · 21 `upsert_category_rule(area_id, pattern, category,
confidence=None)` · 22 `list_category_rules(area_id)` · 23 `save_query_result(table_id, sql,
title, occurred_at)` → doc-Artifact mit Query-Codeblock + serverseitig eingefrorenem
Ergebnis (M-Ersatz).

Falls der Payload-Budget-Guard reißt, Fold-Reihenfolge: `list_category_rules` →
`set_convention` (in describe/Fehlerpfad falten). Count-Guards werden je MCP-WP
fortgeschrieben (58 → 66 → 71 → 81).

## Ingest-Pipeline (B) — synchron, ohne Teilzustand

1. Eingang: Datei (Limit `WHO2BE_INGEST_MAX_BYTES`, Default 20 MB) oder URL.
2. SSRF-Guard (URL): Schema-Allowlist http/https; DNS-Auflösung vor Request; Block
   loopback/private/link-local/multicast/ULA (`ipaddress`-Stdlib); Redirects manuell
   (max. 3), jeder Hop erneut geprüft; Timeout 10 s; Streaming mit Byte-Cap →
   403 `url_forbidden` / 413. Tests ausschließlich MockTransport (Dev-Netz ist policy-geblockt).
3. Typen: PDF, HTML, Text/Markdown; sonst 422 `ingest_unsupported`.
4. Extraktion VOR jedem Write, in memory: PDF via **pypdf**; leer → 422, null persistiert.
   HTML via **beautifulsoup4**: Script/Style/Handler strippen, Heading/Absatz-Struktur →
   Block-Liste (HTML ist nie Quellformat).
5. SHA-256 + Dedup: `wa_blob`-Lookup; gleiche (area, sha256) → idempotent bestehende IDs.
6. Blob-PUT vor DB-Commit (content-addressed → Doppel-PUT harmlos).
7. EINE Postgres-Transaktion: wa_blob-Upsert + Blob-Artifact + Doc-Artifact (Derived Text,
   blob_sha256, source_url/fetched_at, sensitivity) + wa_chunk-Rows. Scheitert sie, bleibt
   höchstens ein MinIO-Orphan — Orphan-Sweep als `who2be-purge`-Erweiterung (>24 h, ohne
   wa_blob-Row).

## Serverlogik Phase 2

- **Timeline (N):** Postgres (`wa_artifact`/`kb_node`, `date_trunc`, precision<>unknown) +
  je Quelle SQLite-Bucket-Aggregat; Merge im Service übers Datum; Rückgabe Zeitscheiben
  `{bucket, items:[{anchor, kind}], counts}` + separater unknown-Bucket; Buckets aus der
  Vereinigung beider Quellen (Tag mit Notizen ohne Transaktionen = volle Scheibe); nie eine
  Kante aus Gleichzeitigkeit persistieren.
- **Kategorisierung (L):** Regel VOR Modell — Kategorie-Wert ohne matchende aktive Regel und
  ohne mitgeliefertes `new_rules`-Element → 422 `rule_required`; neue Regeln werden mit
  `created_by='model:…'|'agent:…'` persistiert, DANN angewandt. Zwei matchende Regeln,
  verschiedene Kategorien → Row unkategorisiert + `kb_conflict(kind='rule')`. Regel-Update →
  serverseitige Re-Kategorisierung (Server unterliegt dem Authorizer nicht) + Audit-Eintrag.
- **M2:** `insert_rows` mit `source_name` ohne `wa_source_convention` → 422
  `convention_missing` (abgelehnt, nicht geraten). Roheingabe = eigenes doc-Artifact
  (via `source_artifact_id` referenziert; jede Row trägt `_source_artifact` in SQLite);
  Korrektur einer Row lässt das Roh-Artifact unangetastet.
- **M-Ersatz:** `query_table` mit `format` + Row-Cap; `save_query_result` führt die Query
  read-only aus und persistiert Query + eingefrorenes Ergebnis serverseitig als
  doc-Artifact. Ein KB-Node über eine Auswertung nutzt `source_ref='artifact:<result_id>'`.
- **O:** `co_occurs_with` verlangt co_query/co_n/co_from/co_to; n<20 → 422
  `correlation_underpowered` (tatsächliches n im detail); aus Gleichzeitigkeits-Evidence nur
  `co_occurs_with`; `update_node(tier='derived')` von hypothesis verlangt
  `additional_source_ref` mit anderem `source_ref_kind`; derived→verified per Update immer
  422 `tier_upgrade_forbidden` (Heben auf verified ist P2-UI-Thema).

## Arbeitspakete (1 WP = 1 Issue = 1 Agent-Session; Wellen datei-disjunkt)

`main.py`-Konfliktvermeidung: alle neuen ProblemReasons/Titel vollständig in WP1;
Router-Includes im jeweils ersten API-WP der Welle.

**Welle 1 — Fundament (parallel):**
- **WP1 Models + Errors + Capabilities:** `who2be_models/{workarea.py,kb.py}` (alle DTOs),
  `errors.py` (13 Reasons), `tool_policy.py` (3 Capabilities + `is_within.bool_fields` +
  Labels), `tool_requirements.py` (nur ReadDomain), `main.py::_PROBLEM_TITLES`.
  Tests: Roundtrips, Anti-Eskalation, Titel-Vollständigkeit.
- **WP2 Migrationen 0073–0077.** Tests: migrated_db-Smoke, Constraints, RLS.
- **WP3 BlobStore + MinIO:** `blobstore/`-Package, minio-Dependency (+mypy-Override),
  Compose (`minio` + `minio-bootstrap`), `.env.example`. Tests: Port-Contract gegen
  memory-Adapter, 503-Pfad. Manuelle Compose-Verifikation (siehe unten).

**Welle 2 — API Phase 1 (WP4 zuerst mergen, dann parallel):**
- **WP4 WorkArea-Core (A+E):** `core/workarea_scope.py`; Router/Service/Repo work_areas +
  wa_artifacts (Block-Split, Anker, rev, append/patch); whoami-Erweiterung; Router-Includes.
  Tests: parallele Patches (200/409+rev), nebenläufige Appends, fremdes privates Artifact →
  404/leer, Capability-403, whoami.
- **WP5 Ingest (B):** wa_ingest Router/Service, wa_blob_repository, pypdf+bs4.
  Tests: PDF ohne Text → 422 ohne Teilzustand, Sanitisierung, Dedup, SSRF-Matrix, 413.
- **WP6 WorkArea-Suche (C):** `services/wa_chunks.py`, `repositories/wa_chunk_repository.py`
  (Scope-CTE vor Ranking), wa_search-Router, Chunk-Sync bei create/append/patch/delete.
  Tests: Anker+Snippet statt Dokument, Grant-Filter in SQL (0 Treffer/Titel/Snippets).
- **WP7 KB (D + E-Sichtbarkeit):** kb-Router/Services/Repos, Anker-Resolver,
  `kb_node_source_area`-Pflege, KB-Suche (0077-tsvector). Tests: Edge ohne Beleg → 422 ohne
  Teilzustand, unauflösbarer Anker → 422, derived→verified → 422, neighbors, Node aus 2
  Areas nur mit beiden Grants, KB-Suche liefert nie WorkArea-Treffer.

**Welle 3 — MCP Phase 1 (WP8 zuerst, dann parallel):**
- **WP8 MCP WorkArea:** `tools/workarea.py` (Tools 1–8), `clients/workarea.py`, `server.py`
  nur `register()`-Hooks, requirements + `_TOOLS`, Count 58→66.
- **WP9 MCP KB:** `tools/kb.py` (9–14), `clients/kb.py`, Count 66→71.
- **WP10 Drift-Guards:** `test_tool_payload_budget.py` (Baseline + Budget + Docstring-Cap),
  REST/MCP-`@contract`-Paritätsfälle, OpenAPI-Golden `REGEN=1`, RLS-Introspektions-Guard
  für alle neuen Tabellen.

**Welle 4 — Fundament Phase 2 (parallel):**
- **WP11 Migrationen 0078–0079 + Modelle** (`who2be_models/tables.py`, Access-Log-DTOs,
  Agent-Modell-Felder in Agent-DTOs).
- **WP12 tablestore-Package:** `tablestore/{engine.py,schema.py,dedupe.py}` (Authorizer,
  query_only, WAL, per-Area-Lock, to_thread, `WHO2BE_TABLESTORE_DIR`, Compose-Volume).
  Tests (DB-los): DROP/UPDATE/ATTACH/PRAGMA-Write → verweigert, Dedupe-Hash,
  10k-Zeilen-Aggregat.

**Welle 5 — API Phase 2 (WP13 zuerst, dann parallel):**
- **WP13 Tabellen-API (K):** wa_tables Router/Service/Repo, describe (Schema, Zeilenzahl,
  min/max), query-Formate + Row-Cap, idempotenter Import, Router-Includes.
  Tests: 403 `query_not_readonly`, Doppel-Import inserted/skipped, 10k-Aggregat ohne Rohzeilen.
- **WP14 Promote (G) + Zugriffslog (F):** `services/wa_promote.py` (ResourceService-Delegation
  + status_history-Note); `repositories/agent_access_log_repository.py` + Log-Aufrufe in den
  Read-/Write-Services (agent-Tokens); Agent-Update-Pfad um model_provider/model_name +
  Audit; Betreiber-Query in `docs/compliance/`. Tests: Promote → Draft nie Active +
  Herkunfts-Note; Log-Dedup pro Tag; sensitivity-Snapshot serverseitig; Betreiber-Query.
- **WP15 Timeline (N):** wa_timeline Router/Service/Repo (Merge beider Stores).
  Tests: Merge, unknown-Bucket, volle Zeitscheibe ohne Transaktionen, Grant-Gate.
- **WP16 save_query_result (M-Ersatz):** in wa_tables-Service (sequenziell nach WP13);
  eingefrorenes Ergebnis + Query-Block als doc-Artifact. Tests: Zahlen stammen aus Result
  Set (Artifact-Inhalt == Query-Output), Provenance.

**Welle 6 — Fachlogik Phase 2 (parallel):**
- **WP17 Regeln + Konventionen (L+M2):** `services/wa_rules.py`, Regel-/Konventions-Routen,
  `rule_required`/`convention_missing`-Gates, Re-Kategorisierung + Protokoll,
  Regel-Konflikt → `kb_conflict(kind='rule')`. Tests: Regel vor Modell, beide 422er,
  Konflikt statt stilles Gewinnen, rückwirkend + protokolliert.
- **WP18 Korrelation (O):** Validierungen in `services/kb.py` (co_-Pflichten, n>=20,
  Tier-Upgrade-Regeln, Fallzahl in neighbors). Tests: n=19 → 422 mit n=19,
  hypothesis→derived nur mit neuem Belegtyp.

**Welle 7 — MCP Phase 2 + Abschluss (parallel):**
- **WP19 MCP Tables/Timeline:** `tools/tables.py` (15–23), `clients/tables.py`,
  Count 71→81, Budget-Guard grün.
- **WP20 Retention/Compliance/Docs:** `core/purge.py` (retention_days-Sweep, Blob-Orphans,
  SQLite-Dateien gelöschter Areas), `gdpr_export_service.py` (Artifacts, Blobs per Prefix,
  SQLite-Dump, KB, Access-Log), `docs/compliance/data-retention-and-erasure.md` + VVT,
  RUNBOOK (MinIO-Backup, `VACUUM INTO`-Snapshots), PROJECT.md-Rahmung, CLAUDE.md §Struktur,
  STATE.md/DECISIONS.md-Pflege.

**Security-Review:** Nach Welle 2 und Welle 5 je ein `security-reviewer`-Durchlauf
(Ingest/SSRF, Area-Grants, SQLite-Authorizer, Zugriffslog) — CLAUDE.md-Pflicht für
externe Inputs/MCP-Tools.

## ADRs (im ersten Umsetzungs-PR)

- **ADR-0047 „Agent WorkArea + Knowledge Base"** (Umbrella): Problem, Abgrenzung zu
  Resources, Datenmodell, Belegpflicht/Tier-Regeln, Area-Grant-/Sichtbarkeitsmodell,
  Zugriffslog inkl. Grenze (kein Runtime-Host → Modell = Agent-Config), Nicht-Ziele.
- **ADR-0048 „Content-addressed Blob-Storage (MinIO/S3)"**: Port, Key-Layout,
  Tenancy-vor-Dedup, AGPL-Container-vs.-Apache-SDK, Degradation, Backup/Purge.
- **ADR-0049 „Tabellen-Store: SQLite pro WorkArea"**: Engine-Wahl (verworfen:
  DuckDB/Postgres-Schema), Authorizer-Enforcement, Katalog-in-Postgres, Timeline-Merge.

## Verifikation

- **Jedes WP (DoD, CONTRIBUTING.md):** `uv run ruff check .` + `ruff format --check` +
  `mypy .` + `pytest --cov --cov-fail-under=85` + pip-licenses-Gate (pypdf BSD-3,
  beautifulsoup4 MIT, minio Apache-2.0 — grün; PyMuPDF/html2text verboten);
  bei Router-Änderungen OpenAPI-Golden `REGEN=1`. CI-Gate ist tot (Actions-Billing) →
  PR-Template mit lokalen Zahlen ist der Merge-Beleg.
- **Drift-Guards neu:** tools/list-Payload-Budget; Tool-Counts 58→66→71→81;
  Policy-Filter-Parität; RLS-Introspektion für neue Tabellen.
- **Manuelle Compose-Verifikation (WP3):** `docker compose up` → minio healthy →
  Bootstrap legt Bucket an und terminiert → ohne Blobstore-Env: Ingest → 503
  `blobstore_unconfigured` → mit Env: PDF-Ingest-Smoke, Objekt unter `blobs/{ws}/{sha}`,
  Doppel-Ingest ohne zweites Objekt.
- **Spec-Akzeptanz → Testfall-Mapping** (vollständig je WP; Auszug): A parallele
  Patches (WP4) · A Privat-Isolation (WP4/6) · B Teilzustand-frei + Dedup (WP5) ·
  C getrennte Indizes (WP6/7) · D Belegpflicht-422 (WP7) · E Capability-403 +
  SQL-Filter (WP4/6/7) · F Zugriffslog + Betreiber-Query (WP14) · G nie direkt
  Active (WP14) · K read-only + 10k-Aggregat (WP13) · L rule_required (WP17) ·
  M2 convention_missing (WP17) · M Zahlen aus Result Set (WP16) · N unknown-Bucket (WP15) ·
  O n<20-422 (WP18).

## Vorgehen nach Freigabe

1. Branch `claude/agent-workarea-kb-plan-755yaw`: diese Plan-Datei als
   `.claude/plan/2026-08-13-<HHmm>_agent-workarea-knowledge-base.md` einchecken + Zeile in
   `.claude/plan/README.md`; ADR-0047/0048/0049 anlegen; DECISIONS.md-Eintrag
   (User-Entscheidungen 1–7); STATE.md-Hinweis. Das ist der erste PR (nur Doku/Plan).
2. GitHub-Issues je WP (WP1–WP20) mit Wellen-Abhängigkeiten aus diesem Plan.
3. Umsetzung wellenweise durch Sub-Agenten (right-sized je Issue), Konsolidierung +
   Integrationstests je Welle, `security-reviewer` nach Welle 2 und 5.
4. Defaults, die ohne Gegenbescheid gelten: Ingest-Limit 20 MB; retention_days-Default
   null (unbegrenzt, auch privat); Tool-Fold-Reihenfolge bei Budget-Riss
   (`list_category_rules` → `set_convention`).
