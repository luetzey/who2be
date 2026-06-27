# STATE — Wo stehen wir (Snapshot, pro Run überschrieben)

_Stand: 2026-06-16_

## Funktioniert

- **Feedback-Views (ADR-0038-Surfacing, 2026-06-27), Branch
  `feat/feedback-views`:** Agenten-Feedback ist jetzt in der Web-UI sichtbar.
  Backend additiv (keine Migration): `GET …/feedback/{type}/{id}/events`
  (Drill-down, ≤50) + `GET …/feedback-overview` (workspace-weit, FULL-OUTER-JOIN
  beider Telemetrie-Tabellen), beide editor-gated. Web: `FeedbackPanel` auf den
  Detailseiten (Persona/Playbook/Resource) mit Verteilungs-Balken, Notizen,
  Lazy-Drill-down + „Überarbeiten"-Aktion; `FeedbackTiles` aufs Dashboard;
  eigene Übersichtsseite `/w/{ws}/feedback` + Nav-Eintrag. **DoD grün:** Python
  891 passed, mypy 296, ruff clean; Web 400 Tests, 0 Lint-Errors, tsc/build clean.
  Offen (bewusst): Triage als append-only Resolution-Event.
- **Track 4-C Write-Rate-Limit (ADR-0039 abgeschlossen, 2026-06-27), Branch
  `claude/track4-finer-rights`:** `AgentToolPolicy.write_rate_limit: int|None`
  (Writes/Min; None=unbegrenzt, JSONB-abwärtskompatibel) + `is_within`-Anti-
  Escalation; Gate `require_write_rate` (Sliding-Window `token_rate_limiter`,
  Key `write:{agent_id}`, 429) nach `require_capability` in allen Write-Pfaden
  von persona/playbook/resource; `whoami` gibt das Limit aus; AgentEditorForm hat
  ein optionales Zahlenfeld. Damit ist ADR-0039 (alle 3 Achsen + Rate-Limit)
  vollständig. **DoD grün:** Python 891 passed, mypy 296, ruff clean; Web 393
  Tests, 0 Lint-Errors, tsc/build clean.
- **Track 4-B Tag-Scoping (ADR-0039, 2026-06-27), Branch
  `claude/track4-finer-rights`:** `AgentToolPolicy.write_tags` (Dict Domain→Tags;
  leer=unrestricted) + `require_write_tags`-Gate in persona/playbook/resource
  create+update+restore (eingehende Tags immer, Bestands-Tags beim Update →
  keine Übernahme out-of-scope). `is_within`-Anti-Escalation. DB-Integrationstest
  grün; volle Suite 888 passed, mypy 296, ruff/Web clean. Offen: UI-Widgets für
  write_tags/transition_grants/Ablauf + Rate-Limit.
- **Track 4-B write_tags-UI + whoami (2026-06-27):** AgentEditorForm hat den
  Tag-Picker (3 Domain-Felder → write_tags-Dict); whoami gibt write_tags +
  transition_grants aus. Web 392 Tests grün, Python 888, mypy 296, ruff clean.
  ADR-0039 komplett: transition_grants-Toggles + Token-Ablauf-Feld im
  Editor/Token-Sektion. Alle 3 Achsen mit Backend+UI. Python 888, mypy 296,
  ruff clean, Web 393/0-Lint/build. Offen nur optionales Write-Rate-Limit.
- **Track 4-B Web-Policy-Editor-Sync (2026-06-27), Branch
  `claude/track4-finer-rights`:** Der `AgentEditorForm` exponiert jetzt die
  feineren Backend-Capabilities `system_prompt_write` (ADR-0040, aus) +
  `feedback_write` (ADR-0038, secure-by-default an) als Write-Switches
  (types.ts/DEFAULT_TOOL_POLICY, useAgentForm-Schema, i18n de/en, Test). Web-DoD
  grün (tsc/lint/391 Tests/build). Offen aus Track 4-B: Tag-Prädikat-Write-
  Scoping (Backend) + UI für transition_grants/Token-Ablauf.
- **Track 4-A feinere Rechte (ADR-0039, 2026-06-27), Branch
  `claude/track4-finer-rights` (gestapelt):** getrennte Promote/Retire pro Domain
  (`transition_grants`, Narrowing von `promote_retire`) + Token-TTL
  (`TokenCreate.expires_at`; Enforcement+Spalte gab es schon). Additiv, DB-frei
  verifiziert. Track 4-B (Tag-Scoping + Web-Policy-Editor) offen.
- **Track 2 Search (ADR-0037, 2026-06-27), Branch `claude/track2-search`
  (gestapelt):** MCP-Tool `search` + `GET /search` — Postgres-Runtime-Volltext
  über Name + Content der aktiven Version, read-scope-gefiltert, nur active.
  Kein Migration (GIN-Index + pgvector als Folge). ruff/mypy clean; eigener PR.
- **Track 3 Feedback-Flywheel (ADR-0038, 2026-06-27), Branch
  `claude/track3-feedback-flywheel` (gestapelt):** append-only `usage_event` +
  `agent_feedback` (Migration 0053, RLS + SELECT/INSERT-only), Capability
  `feedback_write` (default an), Repo/Service/Router + MCP-Tools `record_usage`/
  `submit_feedback`/`get_feedback`. Telemetrie fliesst nie in einen Prompt (kein
  Injection-Vektor). ruff/mypy clean, DB-freie Tests grün; eigener PR.
- **Builder-System-Prompt-Tools (ADR-0040, 2026-06-27), Branch
  `claude/charming-pasteur-pxz2l8`, PR #266:** Der Builder kann System-Prompt-
  Templates über MCP verfassen/anpassen/lesen + draft→review einreichen; das
  Aktivieren (→active) bleibt für Agent-Token hart gesperrt (Injection-Schutz).
  Neue Capability `system_prompt_write` (secure-by-default; Builder-Seed +
  Migration 0052). Neue MCP-Tools `list/get/create/update/restore/transition_
  system_prompt`; Track-1-Versions-Tools decken `entity_type='system_prompt'`
  mit ab. security-reviewer clean. Web-UI-Policy-Toggle → Track 4.
- **AI-native MCP-Ausbau (2026-06-27), Branch `claude/charming-pasteur-pxz2l8`,
  PR #266:** Design für 4 Tracks abgelegt (Plan
  `.claude/plan/2026-06-27-1100_ai-native-mcp-and-rights.md`; ADR-0037 Search,
  ADR-0038 Feedback-Flywheel, ADR-0039 feinkörnige Write-Rechte). **Track 1
  implementiert:** neue MCP-Read-Tools `find_usages`/`list_versions`/
  `get_version`/`diff_versions` (dünne Adapter über bestehende REST-Endpunkte,
  Entity-Dispatch). 12 Tool-Tests + MCP-Suite (111) grün, ruff/mypy sauber.
  Tracks 2/3/4 offen.
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
