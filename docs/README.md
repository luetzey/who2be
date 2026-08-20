# Dokumentations-Index

Einstiegspunkt fuer alles unter `docs/`. Je Eintrag: Diataxis-Typ
(Tutorial / How-To / Konzept / Referenz) und Zielgruppe. Die nach aussen
gerichteten Artefakte (README, CONTRIBUTING, SECURITY, SUPPORT, CHANGELOG,
ROADMAP) liegen im Repo-Root und sind englisch; die interne Doku hier ist
ueberwiegend deutsch (Sprachregel: `docs/standards/coding-standards.md`
bzw. Dokumentations-Standards).

## Referenz

- [`reference/openapi.json`](reference/openapi.json) — versionierte
  OpenAPI-Spec der REST-API (Integratoren; Export:
  `uv run python scripts/export_openapi.py`, interaktiv unter `/docs`
  einer laufenden API)
- [`adr/`](adr/) — Architecture Decision Records (intern; 49 ADRs,
  nummeriert, je Entscheidung eine Datei)
- [`standards/`](standards/) — stehende Engineering-Standards (intern +
  Contributor): [`engineering-method.md`](standards/engineering-method.md)
  (Arbeitsmethode), Coding-, Testing-, Security-, Frontend-,
  Compliance-Standards; Einstieg [`standards/README.md`](standards/README.md)
- [`frontend/design-language.md`](frontend/design-language.md) —
  Designsprache „Warm Citrus": Tokens, Komponenten-Muster, Motion,
  AI-Agenten-Vertrag (intern; vor jeder UI-Aenderung lesen)
- [`frontend/component-map.md`](frontend/component-map.md) —
  Komponenten-Landkarte der Web-UI (intern)
- [`licensing/plans.md`](licensing/plans.md) — Editionen/Tarif-Logik
  (intern)

## Konzept

- [`architecture.md`](architecture.md) — System-Architektur im Ueberblick
  (intern)
- [`agent-axes.md`](agent-axes.md) — Agenten-Achsen: Composite-Playbooks,
  Persona-Modi, Resource-Tags (intern)
- [`frontend/architecture.md`](frontend/architecture.md) +
  [`frontend/i18n.md`](frontend/i18n.md) — Frontend-Architektur und
  UI-Sprachschicht (intern)
- [`compliance/`](compliance/) — Compliance-Paket (Betreiber): VVT,
  C5-Mapping, GoBD-Verfahrensdoku, Loesch-/Aufbewahrungskonzept,
  Agent-Access-Log-Auskunft; Einstieg
  [`compliance/README.md`](compliance/README.md)
- [`signup-and-invites.md`](signup-and-invites.md) — Signup-/
  Invitation-Flow (intern)

## How-To

- [`mcp-claude-code.md`](mcp-claude-code.md) — MCP-Server an Claude
  Code/Claude.ai anbinden (Endnutzer/Integratoren)
- [`mfa-admin.md`](mfa-admin.md) — MFA-Step-up administrieren (Betreiber)
- Smoke-/Verifikations-Runbooks (intern): [`local-smoke.md`](local-smoke.md),
  [`cloud-local-smoke.md`](cloud-local-smoke.md),
  [`cloud-prod-smoke.md`](cloud-prod-smoke.md),
  [`oauth-smoke.md`](oauth-smoke.md),
  [`oauth-e2e-staging.md`](oauth-e2e-staging.md),
  [`oauth-e2e-dokploy.md`](oauth-e2e-dokploy.md),
  [`frontend/smoke-checklist.md`](frontend/smoke-checklist.md)
- Deployment: [`../deploy/hetzner/README.md`](../deploy/hetzner/README.md)
  — Produktions-Deploy inkl. Runbook (Betreiber)

## Arbeits- und Pruefstaende (intern, historisch)

- [`test-plan-functional.md`](test-plan-functional.md) +
  [`frontend/test-plan.md`](frontend/test-plan.md) +
  [`test-agent-prompts.md`](test-agent-prompts.md) — Testplaene
- [`test-runs/`](test-runs/) — protokollierte QA-Laeufe
- [`security-findings.md`](security-findings.md) +
  [`security-findings-phase-2.md`](security-findings-phase-2.md) —
  Security-Reviews (alle Findings geschlossen)
- [`standards-review-2026-07-08.md`](standards-review-2026-07-08.md) +
  [`standards-review-2026-07-20.md`](standards-review-2026-07-20.md) —
  Standards-Audits inkl. offener Owner-Entscheidungen (§4)
- [`codebase-review-2026-05-24.md`](codebase-review-2026-05-24.md) —
  frueher Codebase-Review
- [`frontend/migration-plan.md`](frontend/migration-plan.md) —
  abgeschlossene Frontend-Migration
- [`CLAUDE-PROFILE.md`](CLAUDE-PROFILE.md) — Projekt-Profil fuer
  Claude-Code-Sessions
