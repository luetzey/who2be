# STATE — Wo stehen wir (Snapshot, pro Run überschrieben)

_Stand: 2026-06-16_

## Funktioniert

- Phase 1–3 abgeschlossen: Tenancy, Status-Workflow + Dashboard, Resources +
  BlockNote, Multi-User-RBAC, MCP Read/Write-Tools, Einzel-Delete/Export, i18n.
- Security-Findings (Phase 1 + 2) alle **Closed**, Ampel Grün.
- MCP-HTTP-Transport (ADR-0034) + Per-Request-Bearer + Ein-Klick-MCP-Config;
  Agent-Read-Scope secure-by-default; API-Tokens am Agenten verwaltet.
- **Per-Agent-Connector-URL (ADR-0036-Addendum, 2026-06-25), Branch
  `claude/determined-noether-wi53zd`:** `…/mcp?agent=<uuid>` macht die Connector-URL
  pro Agent eindeutig (Claude-Dedup); `authorize` akzeptiert kanonische Resource oder
  Basis+`?agent=`, Consent sperrt den signierten Agenten hart (client-Wert ignoriert),
  Membership-Prüfung bleibt autoritativ. UI: `AgentConnectorSection` (kopierbare URL,
  kein Token). Security-Review clean; Python/Web-DoD lokal grün; E2E gegen echten
  Claude-Client offen (Fail-safe: ohne Query gilt Consent-Auswahl).
- **OAuth-Remote-MCP-Connector (ADR-0036), Branch `feat/oauth-remote-mcp`:**
  Who2Be ist OAuth-2.1-AS (`apps/api` `/oauth/*` + Metadaten), MCP ist RS
  (FastMCP `RemoteAuthProvider`, PRM/401), Consent-UI (`apps/web`
  `/oauth/consent`). DCR + PKCE + agent-gebundener `w2b_`-Access-Token +
  rotierende Refresh-Tokens. Security-Review durch, Befunde behoben (RLS-Bruch
  in Cloud, Consent-Phishing, Rate-Limits, Refresh-Re-Auth, konstantzeit-PKCE).
- Public-Switch-Vorbereitung: LICENSE.md (FSL-1.1), CONTRIBUTING.md, SECURITY.md;
  Notion-Entkopplung; LLM-Standards-Schicht (`docs/standards/`, `AGENTS.md`,
  `.claude/context/`).
- Lokale Verifikation grün: ruff, mypy strict, Web (lint/tsc/387 Tests/build),
  **gesamte pytest-Suite grün (765 passed, 0 failed)** gegen eine Wegwerf-Postgres.
- **Deploy verdrahtet:** `deploy/hetzner` (api + mcp-http) trägt die OAuth-Env
  (aus `DOMAIN` abgeleitet); README/`.env.example` aktualisiert. Feature greift
  damit im echten Cloud/On-Prem-Deploy (Caddy `api./app./mcp.` + `--profile mcp-http`).
- **OAuth-Smoke beide Editionen grün** (`scripts/oauth_smoke.sh onprem|cloud`,
  Doku `docs/oauth-smoke.md`): voller Flow gegen echten API+MCP-Prozess, Cloud
  als `who2be_app` (RLS aktiv). Fand + fixte einen Cloud-Bug: fehlende
  `who2be_app`-GRANTs auf den OAuth-Tabellen (Migration 0049 ergänzt).

## In Arbeit

- OAuth-Connector: **E2E mit echtem Claude/ChatGPT-Client** steht aus (braucht
  Stack mit `api.`/`app.`/`mcp.`-Subdomains). Offen-Tasks: TTL-Cleanup der
  OAuth-Tabellen, optional Audience-Trennung am RS, MFA/aal2-Consent (Phase 2).

## Bekannte Probleme

- **CI-Runner-Infra defekt:** alle GitHub-Actions-Jobs scheitern in ~2 s,
  `runner_id=0`, keine Logs → mutmaßlich erschöpfte **Actions-Minuten / Billing**
  des privaten Repos. Nicht im Code behebbar. **Public-Flip löst es** (Actions ist
  für öffentliche Repos frei/unbegrenzt).
- E2E-Gate bleibt Soft, bis die CI-Infra steht.

## Nächste Schritte (nicht-Code, manuell beim Owner)

1. CI-Billing klären **oder** direkt auf Public flippen.
2. GitHub-Settings: Description, Topics, Issues/Discussions/Security-Advisories,
   Branch-Protection (CI-grün-Required erst nach CI-Fix).
3. CLA-Assistant aktivieren.
4. Visibility Private → Public (finaler Flip durch den Owner).
