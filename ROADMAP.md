# Roadmap

Kuratierter Ueberblick — Details stehen in `.claude/context/STATE.md`
(laufender Stand), `docs/adr/` (Entscheidungen) und den Plan-Dokumenten unter
`.claude/plan/`. Reihenfolge und Inhalte koennen sich aendern.

## Erledigt (Auszug)

- **Kern-AgentDB:** versionierte Personae, Playbooks (inkl. Composites,
  ADR-0024), Resources mit BlockNote-Editor (ADR-0022), Agents,
  System-Prompt-Templates (ADR-0040), Externe Tools + `tool-ref` (ADR-0043)
- **Tenancy & RBAC:** Organisationen → Workspaces → Entities, Rollen
  `admin > editor > viewer` (ADR-0023), Magic-Link-Invitations, MFA-Step-up
- **MCP-Server:** Read-/Write-/Discovery-Tools, Search (ADR-0037),
  Feedback-Flywheel (ADR-0038), Agent-Memory (ADR-0044), feinkoernige
  Agent-Schreibrechte + Rate-Limit (ADR-0039), Policy-gefiltertes
  `tools/list` (ADR-0042), OAuth-2.1-Remote-Connector (ADR-0036) auf
  HTTP-Transport (ADR-0034)
- **Editionen:** On-Prem vs. Cloud build-isoliert (ADR-0028/0029),
  signierte On-Prem-Lizenzen, optionales Mollie-Billing-Paket
- **Qualitaet & Compliance:** Coverage-Ratchets beide Stacks (ADR-0041),
  OSS-Lizenz-Gates (ADR-0033), Security-Findings Phase 1+2 geschlossen,
  FSL-1.1-Lizenzierung, Deploy-Stack fuer Hetzner (`deploy/hetzner/`)

## Als Naechstes: Public-Switch & erstes Release

Getrackt in den Issues #338–#341:

1. **Owner-Schritte** (#338): GitHub-Actions-Billing (CI-Gate reaktivieren),
   Branch-Protection + Repo-Settings, CLA-Assistant, Visibility-Flip
   Private → Public.
2. **Release-Blocker** (#339): npm-audit-Bereinigung,
   `THIRD-PARTY-LICENSES.md`, dokumentierter Pre-Publish-Nachweis.
3. **Publish-Artefakte** (#340): Code of Conduct, Roadmap, README-Ausbau,
   Changelog, LICENSE-Datei.
4. **Release-Mechanik** (#341): Version `v0.1.0` + GitHub-Release,
   CI-gruener Lauf auf dem Release-Commit, E2E-Journeys scharf schalten.

## Mittelfristig

- **E2E-Haertung:** Playwright-Journeys aktivieren, Soft-Gate
  (`continue-on-error`) entfernen (TST-1)
- **Deploy-Live-Verifikation:** `DEPLOY_HOST` provisionieren und die
  Deploy-Pipeline einmal end-to-end fahren (C1/C4)
- **Architektur-Refactorings** (WP-14-Backlog,
  `docs/standards-review-2026-07-20.md`): `VersionedAggregateService`,
  Repository-Vervollstaendigung, MCP-Modularisierung, `useApiData`,
  A11y-Rest, SBOM (CycloneDX), pre-commit-Hooks
- **OAuth-Connector Phase 2:** TTL-Cleanup, Audience-Trennung, aal2-Consent

## Langfristig / Ideen

- Cloud-Edition produktiv (Mollie-Billing, Entitlements ADR-0028/0029)
- Erweiterte Agenten-Achsen (Persona-Modi, Resource-Tags —
  `docs/agent-axes.md`)
- `1.0.0`, sobald E2E hart, Deploy verifiziert und die API stabil ist

## Mitmachen

Siehe [CONTRIBUTING.md](CONTRIBUTING.md) — externe Beitraege werden mit dem
Public-Switch freigeschaltet.
