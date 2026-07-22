# Changelog

Alle nennenswerten Aenderungen an Who2Be werden in dieser Datei dokumentiert.

Das Format folgt [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionierung folgt [SemVer](https://semver.org/lang/de/). Vor dem ersten
Release (`v0.1.0`) sammelt der Abschnitt „Unreleased" die bisherige
Entwicklung als kuratierte Bloecke; Detail-Historie liegt in den gemergten
Pull Requests und den Plan-Dokumenten unter `.claude/plan/`.

## [Unreleased]

### Added

- **Kern-AgentDB:** versionierte Personae, Playbooks (inkl. Composites),
  Resources mit BlockNote-Editor, Agents, System-Prompt-Templates und
  Externe Tools mit `tool-ref`-Platzhaltern; Status-Workflow
  Draft → Review → Active → Archived mit Diff-/Restore-Funktionen
- **Multi-Tenancy & RBAC:** Organisationen → Workspaces → Entities, Rollen
  `admin > editor > viewer`, Magic-Link-Invitations, MFA-Login-Step-up
- **MCP-Server:** Read-/Write-/Discovery-Tools, Volltext-Search,
  Feedback-Flywheel (`record_usage`/`submit_feedback`), Agent-Memory mit
  Freigabe-Schleuse, feinkoernige Agent-Schreibrechte inkl. Rate-Limit,
  policy-gefiltertes `tools/list`; stdio- und HTTP-Transport mit
  OAuth-2.1-Remote-Connector (Claude Code / Claude.ai)
- **Editionen:** On-Prem (K_pub-verifizierter Lizenz-Key) und Cloud
  (Mollie-Billing-Paket `who2be-billing`), build-isoliert bis ins Web-Bundle
- **Web-UI:** Dashboard mit Status-/Aufmerksamkeits-Band, WorkspaceSwitcher,
  Backlinks, Designsprache „Warm Citrus"
- **Deployment:** Hetzner-Stack (`deploy/hetzner/`) mit Compose, Caddy
  (Auto-HTTPS + Security-Header), Backups und Runbook
- **Qualitaet/Compliance:** Coverage-Ratchets fuer beide Stacks,
  OSS-Lizenz-Gates (fail-closed), Security-Reviews Phase 1+2 geschlossen,
  FSL-1.1-Lizenzierung, `THIRD-PARTY-LICENSES.md` + Generator-Skript

### Security

- npm-audit-Bereinigung im Web-Stack: transitive DoS-/Header-Injection-CVEs
  in `tar`, `undici` und `brace-expansion` (alle nur Dev-Tooling, Production-
  Bundle war nicht betroffen) per Lockfile-Update geschlossen
