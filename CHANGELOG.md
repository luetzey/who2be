# Changelog

All notable changes to Who2Be are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [SemVer](https://semver.org/). Before the first release
(`v0.1.0`), the "Unreleased" section collects the development so far as
curated blocks; detailed history lives in the merged pull requests and the
plan documents under `.claude/plan/`.

## [Unreleased]

### Added

- **Agent work area & knowledge base (ADR-0047/0048/0049):** an unversioned
  workspace per agent (private, plus shared areas via grants) with document
  artifacts, file/URL ingest (20 MB limit, SSRF protection, content-addressed
  blob store with MinIO/in-memory adapters), read-only SQL tables (SQLite per
  area with engine-enforced query budgets), timeline merge, and its own
  search index; plus an evidence-backed knowledge base (source-referenced
  statements, tiers `verified`/`derived`/`hypothesis`, typed edges with
  correlation discipline) — 23 new MCP tools (58 → 81), promotion from work
  area into curated resources as an explicit step, and an automatic agent
  access log with model snapshot for compliance
- **Table UI & exports:** tables tab and table detail page in the web UI
  (schema, conventions, row preview), table export as CSV/XLSX, note export
  as Markdown/HTML plus print-to-PDF; export endpoints with row limit and
  formula-injection guards
- **Semantic search & passage retrieval (ADR-0046):** content chunking with
  per-language full-text configs, `search_content` returns passages instead
  of whole aggregates (REST + MCP), optional local embeddings with hybrid
  RRF ranking and `mode` parameter (`auto|text|semantic|hybrid`), semantic
  agent memory retrieval, backfill CLIs
- **End-to-end test journeys:** Playwright helpers (signup with
  auto-confirm, session injection) and four journeys — persona lifecycle,
  playbook→resource block-ref backlink, agent read-active, invitation
  accept with email-mismatch guard
- **Language as a first-class concept (ADR-0045):** one element = one
  language (`locale` on the identity line of all five content types, with
  badge and list filter; system prompt templates now with language choice),
  workspace content language on creation, automatic output-language
  instruction in the rendered agent system prompt, complete English rollout
  package with locale-aware seeding and boot sync
- **Core AgentDB:** versioned personae, playbooks (including composites),
  resources with the BlockNote editor, agents, system prompt templates, and
  external tools with `tool-ref` placeholders; status workflow
  Draft → Review → Active → Archived with diff/restore
- **Multi-tenancy & RBAC:** organizations → workspaces → entities, roles
  `admin > editor > viewer`, magic-link invitations, MFA login step-up
- **MCP server:** read/write/discovery tools, full-text search, feedback
  flywheel (`record_usage`/`submit_feedback`), agent memory with an approval
  gate, fine-grained agent write permissions including rate limits,
  policy-filtered `tools/list`; stdio and HTTP transport with an OAuth 2.1
  remote connector (Claude Code / Claude.ai)
- **Editions:** on-prem (public-key-verified license key) and cloud
  (Mollie billing package `who2be-billing`), build-isolated down to the web
  bundle
- **Web UI:** dashboard with status/attention band, workspace switcher,
  backlinks, the "Warm Citrus" design language
- **Deployment:** Hetzner stack (`deploy/hetzner/`) with Compose, Caddy
  (auto-HTTPS + security headers), backups, and a runbook
- **Quality/compliance:** coverage ratchets for both stacks, OSS license
  gates (fail-closed), security reviews phases 1+2 closed, FSL 1.1
  licensing, `THIRD-PARTY-LICENSES.md` + generator script

### Changed

- Public repository documents (README, CONTRIBUTING, SECURITY, CHANGELOG,
  ROADMAP) are now in English, following the documentation standards'
  audience rule; a versioned OpenAPI spec is checked in under
  `docs/reference/openapi.json` (export script
  `scripts/export_openapi.py`), and `docs/README.md` indexes the
  documentation tree

### Fixed

- `describe_table` returned 500 once a source convention had been set
  (double JSON encoding via a duplicate row mapper); stored values are
  unpacked by migration, and all three search paths now share one
  full-text-config source
- Work-area search anchors resolved to only the heading block instead of
  the whole passage; index and read path now share the same passage
  boundaries
- Knowledge-base search missed inflected word forms (no stemming); `kb_node`
  is now indexed with the workspace's language config
- MCP error messages dropped the API's machine-readable `reason` codes;
  all error statuses now carry `(reason=…, actionable_by=…)`
- Tables created by agents were unlistable and undeletable over MCP; added
  `list_tables`/`delete_table`, and name-conflict responses now include the
  existing table's ID
- Oversized table cells could be written but made every later read fail
  (`SQLITE_TOOBIG`); writes are now rejected up front against the same
  cell-size limit
- Agent system prompts no longer advertise tools that the agent's policy
  filters out of `tools/list`

### Security

- Phase-2 hardening of the agent work area: per-query time budgets and
  result-size caps for agent SQL, an SQL function allowlist, a
  forgery-proof access log (model config snapshotted at access time,
  protected against cascade deletion), rate-limit checks before query
  execution, and Markdown/CSV injection guards in server-rendered exports
- XLSX/HTML export hardening: formula-injection guard on trimmed copies,
  control-character validation, meta CSP and `no-referrer` in exported
  HTML, and event-loop-safe rendering
- npm audit cleanup in the web stack: transitive DoS/header-injection CVEs
  in `tar`, `undici`, and `brace-expansion` (all dev tooling only, the
  production bundle was not affected) closed via lockfile update
- `react-router`/`react-router-dom` 7.17.0 → 7.18.1 (runtime dependency):
  open redirect via backslash, RSC XSS, SSR hydration constructor
  injection, and route-matching DoS (GHSA-wrjc-x8rr-h8h6,
  GHSA-h8fp-f39c-q6mh, GHSA-337j-9hxr-rhxg, GHSA-chx6-hx7r-mcp5) closed via
  lockfile update
