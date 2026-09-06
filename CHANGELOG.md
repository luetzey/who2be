# Changelog

All notable changes to Who2Be are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [SemVer](https://semver.org/). Detailed history lives in
the merged pull requests and the plan documents under `.claude/plan/`.

## [Unreleased]

### Security

- Issuing or rotating an API token with the `admin` role now requires an
  MFA-verified (aal2) session. Until now the reach of the MFA requirement
  depended on which path you took rather than on what you did: every other
  admin action goes through `require_role(ctx, admin)`, which calls
  `require_aal2` automatically — but *issuing a token that carries admin
  rights* was gated on `editor` only, and the resulting token is itself exempt
  from the MFA gate by design (machine path, like a GitHub PAT). `rotate` is
  gated too and deliberately so: it hands out a new, immediately valid secret
  for the same role, so without it the issuing threshold would have been
  bypassable by rotating an existing admin token — the check runs *before* the
  new secret exists. `rename` and `revoke` stay ungated because neither can
  raise a role. Nothing changes for `editor` and `viewer` tokens, for calls
  made through an existing API token, or for on-premise deployments without an
  `aal` claim, since `require_aal2` already carries both exemptions
  (Issue #469).

### Fixed

- The "stay signed in" marker no longer redirects tabs that are already
  running. It lives in `localStorage`, which is shared across tabs, and the
  storage adapter used to re-read it on *every* access — so signing in with
  the box ticked in one tab silently rerouted an unrelated tab to that other
  session, and clearing the marker logged a remembered tab out without a word.
  The adapter now decides its backend once per tab and keeps it; a login in
  *this* tab updates it, a marker change in a foreign tab does not. A tab
  therefore keeps its mode until it reloads, which is both the fix and the
  intended behaviour. Sign-out got more robust in passing: it no longer
  depends on the marker still being present at the moment the adapter looks
  for the session (Issue #471, ADR-0052 amended).

- The `WHO2BE_SESSION_MAX_AGE_HOURS` runtime setting now reaches the web
  container. The entrypoint has always read it and written it into
  `/config.js`, but neither `web` service passed it in, so an operator who set
  it in `.env` silently got the 12-hour default — no error, no warning. Both
  `docker-compose.yml` and `deploy/hetzner/who2be/docker-compose.yml` now
  forward it exactly the way they already forward `WHO2BE_LAUNCH_MODE`, and
  the notes in both `.env.example` files that described the missing wiring as
  an operator's task are gone. This makes good on what ADR-0052 promised:
  operators can change the absolute session cap without rebuilding the image
  (Issue #470).

### Changed

- API error responses can now carry a stable, machine-readable `reason`
  alongside the German `detail` string, and the web client translates it into
  the UI language (ADR-0051, wave 0 of #402). The addition is strictly
  additive: `detail` is unchanged word for word, the content type stays
  `application/json`, and every call site not migrated in this wave returns a
  byte-identical body — a regression test pins that. The reason vocabulary is
  the *existing* `ProblemReason` literal in `packages/models`, extended by the
  three pilot reasons `agent_not_found` (404), `db_unavailable` (503) and
  `last_workspace_undeletable` (409), rather than a second parallel enum: that
  literal already carried 24 values covering work areas, the knowledge base,
  ingest and blob storage, so it had long stopped being a gate-only vocabulary
  and a second list would have drifted from it. Two *serializations* remain —
  RFC 7807 `ApiProblem` (`application/problem+json`) at the 52 authorization
  and state-machine gates, and the lean `ApiErrorBody` everywhere else —
  because unifying the content type would be a breaking change to the whole
  error contract; since both bodies carry the same `reason`, the client still
  has exactly one translation path,
  `i18n.t('common:errors.' + reason, { ...params, defaultValue: detail })`,
  where an unknown reason falls back to the server text instead of showing a
  raw key. Reasons are raised in the domain services, never assembled in
  routers; `ApiError` subclasses `HTTPException` so status, detail and headers
  behave exactly as before for every caller. `ApiErrorBody` is declared on the
  two pilot routes so the schema appears in `docs/reference/openapi.json`; the
  frozen API surface is unchanged (Issue #436).
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

- A Playwright journey now covers the billing upgrade in a browser: sign in,
  open the billing view, see the current tier with its quotas, trigger the
  upgrade, and assert the app actually starts the redirect to the payment
  provider — with the checkout response intercepted, so the provider is never
  called and no key is needed in CI. It runs in its own CI job against a cloud
  build, because the existing `e2e` job builds the on-premise default where
  the billing UI is tree-shaken out of the bundle entirely; putting it there
  would have meant a test that is skipped forever while looking like coverage.
  A second case asserts a failing checkout surfaces a visible error
  (Issue #453).


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
- An opt-in "Stay signed in ({{hours}} h)" checkbox on the login page (Issue
  #430, default unchecked), so the TOTP prompt on every new tab — the app's
  biggest everyday friction point — becomes a choice instead of a constant.
  Checking it moves that one session from `sessionStorage` (today's
  tab-lifetime behavior, unchanged when left unchecked) to `localStorage` via
  a storage adapter in `lib/supabase.ts` that resolves the backend per access
  from a `who2be.auth.remember` flag — one Supabase client, not two, since
  `createClient` binds its storage once at module scope. A remembered session
  survives a new tab and a full browser restart until an absolute cap
  (`WHO2BE_SESSION_MAX_AGE_HOURS`, runtime-configurable, default 12,
  clamped to 1-24 with a fail-closed default otherwise) that `SessionProvider`
  enforces before ever committing the session at boot; past it, the refresh
  token is invalidated server-side via `signOut()` and the next login goes
  through the full flow again, including step-up. Signing out in one tab
  signs out every other open tab for free — `@supabase/auth-js` already opens
  a `BroadcastChannel` on the session's storage key once `persistSession` and
  `storageKey` are set, which they already were, so no new listener code was
  needed (a tab closed during the sign-out only catches up via the same
  expiry check on its next open, since a `BroadcastChannel` only reaches tabs
  open at the time). `GOTRUE_JWT_EXP` and refresh-token rotation are
  untouched — the cap is a client-side ceiling under the resulting session's
  actual lifetime, not a change to it, and every `aal2` gate on the API
  stays exactly as it was. Replaces ADR-0035 (session storage) with
  ADR-0052, which spells out why an opt-in, capped exception doesn't
  undermine that ADR's XSS reasoning for the default path. The mandatory
  security review found four ways the cap could be silently defeated, all
  fixed here and recorded in the ADR: a login without the box left the
  previous session's refresh token behind in `localStorage`, where — with the
  marker gone — nothing would ever expire it; the marker and its timestamp
  lived in two keys, so a missing or unparseable timestamp meant no cap at
  all; a slow in-flight session commit could land after a forced expiry
  logout and undo it; and a marker left over from an earlier session was
  inherited by logins that never offered the checkbox. The marker is now a
  single atomic value that counts as expired whenever no valid timestamp can
  be read from it, the expiry check runs before every commit rather than only
  at boot, the superseded backend's session copy is purged on every mode
  switch, and any `SIGNED_OUT` — from any source — clears the marker.
- A personal favorite star on every agent card (Issue #427), and a "Favorites"
  group above the rest of the list. The state is per user and server-side, so
  it survives a reload and follows the user to another browser — two members of
  the same workspace see different stars. That ruled out the two cheaper
  options: a column on `agent` would have been workspace-wide, `localStorage`
  would not survive a device change. The new `agent_favorite` table carries
  `workspace_id` denormalized so the tenant-isolation policy can read it off
  the row without a join, and it has no foreign key on the user because no
  table in the schema references the GoTrue user; account deletion therefore
  clears the rows explicitly in `purge_account_data` rather than by cascade.
  `GET .../agents` gained an `is_favorite` field, filled from the same single
  batch roundtrip that already fills the card pills, so the list did not get a
  second query. Setting and clearing it are `PUT` and `DELETE` on
  `.../agents/{id}/favorite`, both idempotent and both open to every workspace
  member including `viewer` — a favorite is a private note, not workspace
  content — while agent-bound API tokens get a 403, since a token has no
  favorites list of its own. MCP `list_agents` deliberately does not carry the
  star: on a token path `ctx.user_id` is the *human who owns the token*, so
  passing it through would have shown a remote LLM connector which agents that
  person had marked, and made `list_agents` answer differently per token owner.
  Machines get no favorites list at all, which is what the write path already
  said by refusing agent-bound tokens. Removing a member from a workspace
  clears their stars in the same transaction, and the Art. 15/20 export carries
  them alongside the deletion path, filtered to the requesting user so it never
  hands out anyone else's.

### Fixed
- Dialogs, sheets, dropdowns, popovers and tooltips fade and slide again
  (Issue #465). They carried 42 animation classes that produced no CSS at all:
  `tailwindcss-animate` was declared as a dependency but never loaded, and
  Tailwind v4 has no config file to load it from. Enabling the plugin turned
  out to be the wrong fix, and measurably so — it writes its duration as
  `animation-duration: .15s` directly into the variant rule
  (`.data-[state=open]:animate-in[data-state=open]`), which has higher
  specificity than a flat `duration-[var(--duration-*)]` utility, so the design
  token could never win; and it redefines `duration-*` to also set
  `animation-duration`, which would have reached all 31 existing uses that mean
  transition duration. The motion is therefore built from own keyframes in
  `globals.css`, driven by Radix's `data-state` so each component carries one
  class instead of six variants, with duration and easing read straight from
  the motion tokens. The unused dependency is gone. Measured in Chromium: 200 ms
  emphasized for the dialog, 320 ms for the sheet, 120 ms standard for the
  smaller overlays, and 0.01 ms under `prefers-reduced-motion: reduce`, so the
  global safety net still holds. `docs/frontend/design-language.md` §7 said
  `slow` for dialogs in one table and `medium` in the other; the code already
  used `medium`, so §7.3 wins and §7.1 was corrected, with the previously
  missing rows for sheet, popover and tooltip added.

- Three leftovers from the #452 security review on the generic billing webhook
  (Issue #463). `include_routers` now decides whether to mount the webhook from
  the `Settings` it is handed rather than from a `get_settings()` call of its
  own — the caller already held that object and used it one line above, so the
  self-call was the deviation; it meant a `create_app(settings=…)` carrying a
  different `billing_webhook_secret` mounted according to the environment
  instead. The generic path now logs a rejected signature (WARNING), a dedupe
  no-op (INFO, a provider retry is normal, not an error) and a released claim
  (ERROR, the one state that can need a human) — carrying the event id and the
  provider, never the header value or the payload, since both are
  attacker-controlled and a log with raw values turns the finding into a data
  leak. And `_parse_stripe_header` converts the `t=` value through the existing
  `_coerce_int` helper: the old `value.isdigit()` guard was both too permissive
  and too naive, because `"²".isdigit()` is `True` while `int("²")` raises, and
  a very long digit string trips CPython's ~4300-digit integer conversion
  limit — either one propagated out as an unhandled exception. Negative values
  stay rejected as before, so the endpoint's outward behaviour is unchanged.
  Points 1 and 3 of the original finding remain open by design; they are
  trade-offs awaiting an owner decision, not conventions to apply.

- `deploy/hetzner/.env.example` now carries `MINIO_ROOT_PASSWORD` (Issue #458).
  It was the one value the template never had, and the `minio` service reads it
  with no default on purpose — an object store with standard credentials on a
  public machine is an open door, so the compose stack refuses to start without
  it. The effect was that an operator following `deploy/hetzner/README.md`
  copied the template to `.env` and got a stack that would not even resolve,
  with an error naming the variable but not the fact that the template had
  never carried it. All three documented overlay combinations (base, `+cloud`,
  `+local`) now resolve against the template with nothing exported into the
  shell. The `:?` guard is untouched and still aborts on an empty value;
  `MINIO_ROOT_USER` is deliberately left out, since it has a default at all
  three read sites and listing it would imply a requirement that does not
  exist.


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
