# Changelog

All notable changes to Who2Be are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [SemVer](https://semver.org/). Detailed history lives in
the merged pull requests and the plan documents under `.claude/plan/`.

## [Unreleased]

### Changed

- `docs/licensing/plans.md` and the `BillingPanel` now describe Free and Pro
  by what the code actually enforces — price, MCP requests/month, MCP
  requests/minute and the per-workspace entity limit — instead of listing the
  `composite_playbooks`, `agents` and `audit_export` feature codes as
  purchasable Pro capabilities. No code path gates on those individual codes
  (`audit_export` has no endpoint at all); the only thing `Entitlement.
  entity_limit()` actually reads is whether *any* paid feature code is present
  at all, which lifts the entity limit from 50 to unlimited. The docs now say
  so explicitly, and the codes stay documented as entitlement metadata rather
  than being silently dropped, since they still surface in the `whoami` and
  `entitlement` MCP/API responses (Issue #449). In the panel, the removed
  `PRO_FEATURES` array is replaced by two separate checks against a small
  `TIERS` list (also the source for the newly shown price and entity-limit
  fields), each with the robustness its job needs: whether the plan is paid at
  all (gates the upgrade CTA) is a *threshold* on `mcp_monthly_quota` — above
  the Free quota, or `null` (unlimited, as with a `manual_override` grant or
  On-Prem) — so a support override with a one-off quota still reads as paid
  instead of showing the upgrade button; which tier exactly (drives the shown
  name/price/entity-limit) stays an *exact* match, falling back to "unknown"
  display text when no tier fits. A future third tier is a new list entry
  rather than a panel rewrite. No backend change: `licensing/entitlement.py`
  and `packages/billing/.../plans.py` are untouched, and prices/limits are
  unchanged.
- Hetzner Cloud deploys now pull the `api` and `migrate` services as prebuilt
  images from GHCR (`ghcr.io/luetzey/who2be-api-cloud:<sha>`, the same
  `runtime-cloud` artifact CI already built and pushed) instead of building
  them on the production host from source. `deploy.sh` pulls `api`, `migrate`
  and `web` in the cloud branch (previously only `web`); `web` keeps its local
  build because there is no `web-cloud` image (ADR-0029 tree-shakes the
  billing UI at compile time). `deploy/hetzner/RUNBOOK.md` documents the
  host-build fallback for when the registry is unreachable (#450).
- Running Who2Be locally now needs nothing but Docker: `docker compose up -d
  --wait` brings up the whole stack, no `.env` file, no uv and no Node. The web
  UI resolves its API and auth URLs at runtime (`/config.js`, written from the
  container's environment) instead of having them compiled into the bundle, and
  the web container forwards `/v1/` and `/auth/v1/` to the origin it was served
  from. As a result the stack is reachable from another device on the network —
  `WHO2BE_PUBLIC_URL=http://<host-ip>:5173 docker compose up -d --wait` — with
  no rebuild; previously every browser was sent to its own `localhost` and the
  app was dead outside the host machine. The published web image is host-neutral
  for the same reason: deployments now pass `WHO2BE_API_BASE_URL`,
  `WHO2BE_SUPABASE_URL` and `WHO2BE_SUPABASE_ANON_KEY` as container environment
  rather than build arguments.

### Added

- The MCP server now runs as part of the local stack (`mcp` service, Streamable
  HTTP on `localhost:8765/mcp`, also reachable behind the web origin at `/mcp`).
  Until now the only local option was `uv run python -m who2be_mcp.server` — the
  Python toolchain the one-command start removes — which left Who2Be's central
  feature untestable for anyone who just wanted to try it. It authenticates with
  an ordinary `w2b_` token, so no OAuth setup is involved.
- `docker-compose.images.yml` — an overlay that pulls the prebuilt
  `ghcr.io/luetzey/who2be-*` images instead of building from source, which skips
  the multi-minute first build.
- A `WHO2BE_LAUNCH_MODE=coming_soon` runtime switch (Issue #429) puts the app
  into a "we're still building this" mode without a rebuild: `/signup` shows a
  bilingual (DE/EN) notice page instead of the sign-up form, and the login
  page's "Sign up" link points there instead of disappearing. An optional
  `WHO2BE_LAUNCH_CONTACT` address is shown on the notice page. The real
  enforcement stays `GOTRUE_DISABLE_SIGNUP` (unchanged) — this only controls
  the web UI, and `scripts/smoke.sh` now fails loudly if the two disagree
  (`coming_soon` set but GoTrue still accepts `signUp`). The older
  `WHO2BE_SIGNUP_DISABLED` / `VITE_WHO2BE_SIGNUP_DISABLED` switches keep
  working unchanged (now documented as deprecated) for anyone not ready to
  move to the new variable.
- A chain test (`packages/billing/tests/test_checkout_webhook_entitlement_limit_chain.py`)
  now drives the whole paid path end-to-end: start a Mollie checkout, simulate
  the webhook ping for the resulting first payment, and show that the same MCP
  request which the Free-tier default (`CLOUD_FREE_ENTITLEMENT`) rejects with
  429 goes through once the webhook has written the Pro entitlement — with a
  negative control (no webhook ⇒ still rejected) right next to it. Checkout,
  webhook mapping, the entitlement write path and the MCP rate/quota gate each
  already had their own tests, but nothing showed that a paid subscription
  actually unlocks a higher limit end-to-end. The test runs without a database
  (no Docker in CI's non-integration jobs) by backing the real
  `PgEntitlementRepository` and `PgMcpUsageRepository` with an in-memory stub
  connection pool instead of mocking those repositories themselves — only the
  DB connection and the Mollie API (`FakeMollieGateway`, as in
  `test_mollie_adapter.py`) are faked; the entitlement decision logic
  (`Entitlement.is_active()`, quota comparison, `increment_if_allowed`) runs
  unmodified. The checkout endpoint also gets its first HTTP-level test
  (`test_checkout_success_returns_201_with_mollie_metadata`): 201 plus the
  metadata actually handed to the (fake) Mollie gateway, where previously only
  its rejection paths were covered over HTTP.
- `scripts/smoke.sh` gained an eighth check: the generic billing webhook route
  (`POST /v1/billing/webhook`) answers 400 (fail-closed, no signature) against
  a Cloud deployment and 404 against an On-Prem one, proving the route itself
  is edition-gated. The check needs neither `MOLLIE_API_KEY` nor a configured
  webhook secret — it only exercises the fail-closed signature check, never a
  real Mollie call — so it can't go red for reasons unrelated to routing.
- Groundwork for the upcoming mobile UI waves (Issue #438), with no consumer
  wired up yet: a "Responsive & Breakpoints" section in
  `docs/frontend/design-language.md` (§4.4) documents the Tailwind-default
  breakpoint scale, the mobile-first rule, and a review checklist for
  multi-column grids and fixed widths; `hooks/useMediaQuery.ts` adds
  `useMediaQuery(query)` and `useIsMobile()` (the `< md` threshold), guarded
  the same way as `ThemeProvider`'s `matchMedia` check so it degrades to
  `false` without a `matchMedia` implementation; and
  `components/ui/sheet.tsx` adds a shadcn-style `Sheet` slide-in panel built
  on the same `@radix-ui/react-dialog` primitive `dialog.tsx` already uses,
  with `side: left | right | top | bottom` variants.

### Fixed

- Looking a persona up by name over MCP (`get_persona("Builder")`) could abort
  with an opaque tool error, while the same persona resolved fine by UUID. The
  name path fetched the *entire* persona list and compared names client-side —
  and because a persona read carries its full body, that dragged every persona's
  written-out text across the wire to match a single string. A single persona
  can render past 119,000 characters, so the response outgrew the client's
  10-second timeout. `GET /v1/workspaces/{id}/personas` now accepts an exact
  `?name=` filter and the MCP client uses it, turning the lookup into one narrow
  request. The client-side name check is deliberately kept as a safety net: an
  older API ignores the unknown parameter and returns the full list, and without
  that check the first persona in the list would be returned as a false match.
- The same name lookup ignored the list endpoint's pagination — no `limit` was
  sent and `X-Next-Cursor` was never followed — so beyond 100 personas it would
  report "no persona named X" for a persona that exists. The server-side filter
  removes the problem rather than papering over it: the filtered result is one
  or two rows, far below the page limit.

- An MCP connector whose token belongs to a **second** workspace failed on every
  single tool with `403 Token gehoert nicht zu diesem Workspace` — `whoami`
  included. The MCP server took the workspace for its `/v1/workspaces/{id}/...`
  path from `GET /v1/me` → `default_workspace_id`, which is the caller's *first*
  membership (ordered by organization age) and carries no token binding at all,
  so a token pinned to workspace B was sent to workspace A. `GET /v1/me` now also
  reports `token_workspace_id` (the binding of the calling credential, `null` for
  JWT auth), and the MCP server prefers it, falling back to
  `default_workspace_id` only for unbound credentials. Anyone with more than one
  workspace was affected deterministically.
- Cross-workspace token reuse now answers with the taxonomy reason
  `workspace_mismatch` and `actionable_by: "human"` instead of
  `forbidden_transition` / `"none"`. The old code belongs to the version status
  machine, so agents branching on `reason` — which the taxonomy invites them to
  do — were told a status transition had been refused.
- **Security:** setting `WHO2BE_WORKSPACE_ID` together with
  `WHO2BE_TRANSPORT=http` is now rejected at startup. The HTTP transport is
  multi-tenant (one process serves every bearer), where a pinned workspace would
  override the binding of *every* incoming token. The pin remains available for
  single-tenant stdio use.
- **Security:** the OAuth consent endpoint no longer accepts `w2b_` API tokens —
  it now requires a signed-in web session. It read only the caller's user id and
  ignored the token's workspace, role and agent pins, and because `/oauth/*` sits
  outside the workspace-scoped prefix nothing else enforced them. Since the token
  a consent mints derives its role from the user's current membership rather than
  the calling token's pinned snapshot role, a deliberately downgraded `viewer`
  token could register its own client and mint an `admin` one, escaping its
  workspace and tool-policy pins along the way — and the resulting refresh chain
  survived revocation of the original. Consent is a human decision point; a
  machine must not pass it on its own behalf.
- Declining an OAuth connection works again when no agent can be resolved. The
  agent id was a required field, so "deny" failed validation before it reached the
  server and the client never received its `access_denied` redirect.

- The OAuth consent screen now names the agent it is about to bind, together
  with its workspace, instead of showing a bare UUID. It only ever listed agents
  from your default workspace, while the server resolves across every workspace
  you belong to — so an agent living elsewhere showed up unreadable, and if your
  default workspace happened to be empty the consent could not be completed at
  all. When the agent cannot be resolved for your account, the approve button is
  now disabled with a reason rather than failing with a generic error.

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

### Security

- Hardened the generic `POST /v1/billing/webhook` path (Stripe-style HMAC
  format; no configured provider sends to it today — the repo only wires up
  `mollie-api-python`, and Mollie doesn't sign). A grant event without a
  resolvable billing period is now rejected instead of silently producing an
  entitlement with no expiry, which used to bypass the expiry check entirely;
  an unlimited entitlement is now only reachable through the OSS/on-prem
  default. The same envelope event id is now deduplicated through the
  `ProcessedEventRepository` ledger the Mollie path already uses — claimed
  before the entitlement upsert and released again if the upsert fails, so a
  duplicate delivery is acknowledged as success without a second write or
  journal row. The generic HMAC format now also enforces the signature replay
  window (read from the event payload's `created` field, since — unlike the
  Stripe format — its header carries no timestamp); the header format itself
  is unchanged. The route is now only mounted when `billing_webhook_secret` is
  configured, so a missing secret answers 404 instead of 400. The Mollie path
  (`mollie.py`) is untouched (Issue #452).

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
