# Changelog

All notable changes to Who2Be are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [SemVer](https://semver.org/). Detailed history lives in
the merged pull requests and the plan documents under `.claude/plan/`.

## [Unreleased]

### Fixed

- The language switcher is now reachable on the pages you see before signing
  in. It lived only in the app shell, while every public route — sign-in,
  sign-up, password reset, invitation onboarding, the OAuth consent screen and
  the legal pages — sits outside that shell. The English strings were complete
  all along; there was simply no way to switch to them, so the browser's
  language decided. An invited user whose browser is set to German landed on a
  German onboarding page with no recourse.
- `<html lang>` now follows the active language. It was hard-coded to `de` and
  never updated, so an English UI still declared itself a German document —
  screen readers pick their pronunciation from it and browsers base their
  translation offer on it.

- Connecting a remote MCP connector no longer asks you to pick an agent again.
  The per-agent connector URL now carries the agent in its path
  (`.../mcp/a/<uuid>`) instead of a query (`?agent=<uuid>`). LLM clients take the
  RFC 8707 `resource` parameter from the MCP server's RFC 9728 protected
  resource metadata, which advertises the canonical URL and drops the query — so
  the agent hint never reached the authorization server and the consent screen
  fell back to its agent dropdown. A path is part of the resource identity and
  survives. The MCP server advertises a per-agent metadata document and maps the
  path onto its canonical endpoint; existing `?agent=` URLs keep working.
- The authorization server now accepts an agent UUID only in canonical
  8-4-4-4-12 form, matching the resource server. `uuid.UUID()` also accepts
  `{...}`, `urn:uuid:...` and hyphen-less forms, which would have given one agent
  several connector identities that the resource server never advertises.

- The language switcher no longer loses the user's choice. The stored
  cross-device preference (`user_metadata.preferred_locale`) is now a starting
  value, not a running source of truth: an explicit choice in the current tab
  wins, while a different user signing in on the same device still gets their
  own preference. Two paths caused the revert — the asynchronous session
  bootstrap (the header switcher is usable before `session.user` arrives), and
  `supabase.auth.updateUser` keeping the existing `access_token`, which made the
  session provider's token-based deduplication drop the `USER_UPDATED` event.
- Translated strings are no longer frozen at module load. Zod validation
  messages resolved `i18n.t(...)` in module-level schema literals, so they kept
  whatever language happened to be active when the route chunk first loaded and
  ignored later switches. They now use Zod 4's lazy `{ error: () => … }` form.

### Added

- English translations for the previously German-only parts of the web UI: the
  complete system prompt editor (slash menu including its search aliases, all
  seven pickers, placeholder preview), dashboard attention banners and quick
  start, toast and error messages across hooks, `lib/` and the API client, and
  the remaining validation messages. Placeholder labels that are written into
  the document stay language-stable — they are content and follow the element's
  language (ADR-0045), not the interface language.

## [0.1.0] - 2026-08-20

First public release. This section collects the entire development up to
the public switch as curated blocks.

### Added

- Tag grouping for the playbook list and, for the first time, grouping on
  the resource list (client-side, multi-tag membership with an "untagged"
  group)
- Policy presets in the agent editor ("Read only" / "Editor without
  approval" / "Editor with approval"), derived from and applied to the
  write-capability checkboxes; deviations show as "Custom"
- `data-testid="branch-action-*"` anchors on the shared status action bar
  (submit/publish/reject/reactivate), used by the end-to-end journeys
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

- Persona and playbook detail pages now use the shared status action bar
  with a per-page label override — visible button and toast texts are
  unchanged
- MCP write-tool docstrings document the persona mode schema and the
  canonical BlockNote body/pill format for playbooks and resources
- Python minor/patch dependency updates (FastAPI 0.141.1, fastmcp 3.4.7,
  pydantic-settings 2.15.0, redis 8.1.0, pypdf 6.16.1; dev tooling: pytest
  9.1.1, mypy 2.3.1, ruff 0.16.3)
- Public repository documents (README, CONTRIBUTING, SECURITY, CHANGELOG,
  ROADMAP) are now in English, following the documentation standards'
  audience rule; a versioned OpenAPI spec is checked in under
  `docs/reference/openapi.json` (export script
  `scripts/export_openapi.py`), and `docs/README.md` indexes the
  documentation tree

### Fixed

- End-to-end journeys run for real now: session upgrade to AAL2 via an
  actual TOTP enrollment, promote-ready seed data, and corrected selectors;
  the e2e CI job is a hard gate (was soft)
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

- All GitHub Actions in the CI/deploy workflows are pinned to full-length
  commit SHAs (supply-chain hardening, satisfies the repository's actions
  policy)
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
