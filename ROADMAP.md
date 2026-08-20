# Roadmap

Curated overview — details live in `.claude/context/STATE.md` (running
state), `docs/adr/` (decisions), and the plan documents under
`.claude/plan/`. Order and contents may change.

## Done (excerpt)

- **Core AgentDB:** versioned personae, playbooks (including composites,
  ADR-0024), resources with the BlockNote editor (ADR-0022), agents,
  system prompt templates (ADR-0040), external tools + `tool-ref`
  (ADR-0043)
- **Tenancy & RBAC:** organizations → workspaces → entities, roles
  `admin > editor > viewer` (ADR-0023), magic-link invitations, MFA step-up
- **MCP server:** read/write/discovery tools, search (ADR-0037), feedback
  flywheel (ADR-0038), agent memory (ADR-0044), fine-grained agent write
  permissions + rate limit (ADR-0039), policy-filtered `tools/list`
  (ADR-0042), OAuth 2.1 remote connector (ADR-0036) on HTTP transport
  (ADR-0034)
- **Agent work area & knowledge base (ADR-0047/0048/0049):** unversioned
  workspace per agent (documents, file/URL ingest with content-addressed
  blob store, read-only SQL tables, timeline), evidence-backed knowledge
  base with typed edges, promotion into curated resources, agent access
  log; 81 MCP tools in total, table UI + CSV/XLSX/Markdown/HTML exports
- **Semantic search & passage retrieval (ADR-0046):** content chunking,
  `search_content` passages, optional local embeddings with hybrid RRF
  ranking, semantic agent memory
- **Language as a first-class concept (ADR-0045):** one element = one
  language, locale badges + filters, English rollout package with
  locale-aware seeding
- **Editions:** on-prem vs. cloud, build-isolated (ADR-0028/0029), signed
  on-prem licenses, optional Mollie billing package
- **Quality & compliance:** coverage ratchets for both stacks (ADR-0041),
  OSS license gates (ADR-0033), security findings phases 1+2 closed,
  FSL 1.1 licensing, deploy stack for Hetzner (`deploy/hetzner/`)

## Next: public switch & first release

Tracked in issues #338–#341:

1. **Owner steps** (#338): branch protection + repo settings, CLA
   Assistant, visibility flip private → public. (The CI gate used to be
   listed here — it has been running again since 2026-08-16.)
2. **Release blockers** (#339): npm audit cleanup,
   `THIRD-PARTY-LICENSES.md`, documented pre-publish evidence.
3. **Publish artifacts** (#340): code of conduct, roadmap, README
   expansion, changelog, LICENSE file.
4. **Release mechanics** (#341): version `v0.1.0` + GitHub release, a green
   CI run on the release commit, activating the E2E journeys.

## Mid-term

- **E2E hardening:** activate the Playwright journeys, remove the soft gate
  (`continue-on-error`) (TST-1)
- **Deploy live verification:** provision `DEPLOY_HOST` and run the deploy
  pipeline end-to-end once (C1/C4)
- **Architecture refactorings** (WP-14 backlog,
  `docs/standards-review-2026-07-20.md`): `VersionedAggregateService`,
  repository completion, MCP modularization, `useApiData`, remaining a11y,
  SBOM (CycloneDX), pre-commit hooks
- **OAuth connector phase 2:** TTL cleanup, audience separation, aal2
  consent

## Long-term / ideas

- Cloud edition in production (Mollie billing, entitlements ADR-0028/0029)
- Extended agent axes (persona modes, resource tags — `docs/agent-axes.md`)
- `1.0.0` once E2E is hard, deploy is verified, and the API is stable

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) — external contributions open with
the public switch.
