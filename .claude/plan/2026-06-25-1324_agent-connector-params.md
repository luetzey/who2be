# Plan — Connector-Parameter am Agenten (kopierbar, OAuth, ohne Token)

_Erstellt: 2026-06-25 13:24 · Branch: `claude/determined-noether-wi53zd`_

## Ziel / Outcome

Der User soll auf der **Agent-Detail-Seite** die fertigen Verbindungsparameter
für einen **Claude-Remote-Connector (OAuth)** sehen und mit einem Klick kopieren
können — pro Agent eine **eindeutige URL**, damit Claude den Connector nicht als
Duplikat ablehnt („A server with this URL already exists"). **Kein Token** im
Connector/Systemprompt — die Autorisierung läuft weiter über den OAuth-Consent.

## Repo-Fakten (verifiziert)

- Scoping ist **agent-gebunden über den Token** (`core/agent_scope.py`,
  Policy-Default `assigned`). Welcher Agent → welche Playbooks entscheidet der
  beim OAuth-Consent ausgestellte `w2b_`-Token, **nicht** die URL.
- OAuth-`authorize`/`consent` erzwingen `resource == mcp_resource_url`
  **exakt** (`services/oauth_service.py:143` und `:171`). `mcp_resource_url` ist
  `https://mcp.<domain>/mcp` — **ohne** Query.
- Der Agent wird heute im **Consent-Dropdown** gewählt
  (`OAuthConsentPage.tsx`), Default = erster Agent.
- Es existiert bereits ein **token-basierter** Config-Copy (mcp-remote-Bridge,
  `lib/mcpConfig.ts` / `McpConfigCopy.tsx`) — das ist der *andere* Pfad (Header-
  Token), nicht der OAuth-Connector.
- Web kennt die Basis-URL als `config.mcpUrl`.

## Design-Weiche (Kern der Entscheidung)

Damit N Connectoren (einer pro Agent) je eine **eindeutige URL** haben und
**gleichzeitig** OAuth nicht bricht, braucht jede einen (URL, resource)-Wert,
der die exakte `resource`-Prüfung übersteht.

- **Option A — `?agent=<uuid>` als Query (empfohlen).** Web zeigt
  `${mcpUrl}?agent=${agentId}`. Backend lockert die `resource`-Prüfung minimal:
  akzeptiert `mcp_resource_url` **oder** `mcp_resource_url?agent=<uuid>` (Basis
  muss exakt passen, nur der Schlüssel `agent` mit gültiger UUID erlaubt →
  Audience-Kette bleibt zu). Der Agent-Hint wird in den signierten Blob
  übernommen und der Consent **wählt diesen Agenten vor**.
  - *Fail-safe:* Schickt Claude die kanonische PRM-Resource (`…/mcp` ohne
    Query), bleibt alles wie heute (User wählt im Consent) — **nichts bricht**.
    Schickt Claude die Connector-URL als `resource`, wird der Agent vorausgewählt.
  - Eindeutige URL je Agent → Claude-Dedup zufrieden; ein Deployment, keine
    Infra pro Agent; „copy & paste" erfüllt.
  - *Trade-off:* Pre-Select ist gegen echten Claude-Client hier **nicht
    E2E-verifizierbar** (STATE: E2E steht aus, CI-Infra defekt). Der Fail-safe
    macht das Risiko aber auf „funktioniert wie heute" begrenzt.
- **Option B — Subdomain pro Agent** (`mcp-<x>.<domain>/mcp`). Sauberste
  Audience-Trennung + eigener Tool-Namespace, aber **Infra pro Agent** (DNS,
  Caddy-Route, MCP-Instanz, Env). Kein „copy a URL". Verworfen für dieses Ziel.
- **Option C — Pfad-Segment** (`/mcp/a/<uuid>`). MCP-Server müsste Catch-all
  mounten + PRM/Resource pro Pfad advertisen. Mehr Server-Arbeit. Verworfen.

**Empfehlung: Option A.**

## Entscheidungen (User, 2026-06-25)

- **Scope:** Frontend + Backend-Fail-safe.
- **Consent-Verhalten:** Agent-Hint aus der URL **hart sperren** — trägt die
  `resource` einen `?agent=<uuid>`, bindet der Consent **genau diesen** Agenten
  (kein Dropdown-Wechsel). Trust-Anker ist die **signierte** Blob-`agent_id`,
  nicht der client-gesendete Wert. Passt der Agent zu keiner Membership des
  Consent-Users → klarer Fehler (kein Silent-Fallback).

## Arbeitspakete (bei Zustimmung zu Option A / Scope 2)

### WP1 — Backend OAuth (sicherheitsrelevant → `security-reviewer`)
- `services/oauth_service.py`: Helper `_match_resource(resource) -> agent_id|None`,
  der die Basis exakt gegen `mcp_resource_url` prüft und genau einen optionalen
  `?agent=<uuid>` zulässt (UUID-Format validiert; sonst `invalid_target`).
  An `:143` und `:171` einsetzen; `agent_id`-Hint in den Blob (`authorize_to_consent_url`).
- `consent(...)`: liegt ein gültiger Agent-Hint vor und gehört er zu einer
  Membership des Users, als Default/Vorauswahl nutzen (kein Hard-Lock bei
  Mismatch — graceful).
- Tests: `tests/test_oauth.py` — Resource mit/ohne `?agent=`, ungültige UUID,
  fremder Agent, Blob-Roundtrip, Pre-Select.

### WP2 — Web Agent-Detail „Connector"-Card
- Neue Komponente `features/agents/components/AgentConnectorSection.tsx`:
  zeigt Connector-Name-Vorschlag (`Who2Be – <AgentName>`), Server-URL
  `${config.mcpUrl}?agent=${agent.id}` (read-only + Copy), Auth-Hinweis
  „OAuth-Login, kein Token". In `AgentDetailPage.tsx` einhängen.
- i18n `de.json`/`en.json` (`agents`-Namespace).
- Vor UI-Arbeit: `docs/frontend/design-language.md` lesen; Primitives aus
  `@/components/ui/*`, keine rohen `<button>`/`<input>`.
- Tests: Komponententest (URL korrekt, Copy ruft Clipboard).

### WP3 — Consent-Vorauswahl (Web)
- `OAuthConsentPage.tsx`: Agent-Hint aus dem Request-Blob lesen
  (`readBlobInfo` erweitern) und Dropdown-Default darauf setzen, statt immer
  `list[0]`. Test ergänzen.

### WP4 — Doku
- ADR-Notiz (Erweiterung ADR-0034/0036: `?agent=`-Resource-Variante),
  `.claude/context/STATE.md` + `DECISIONS.md` pflegen.

## DoD
- Python: `uv run ruff check .`, `uv run mypy .`, `uv run pytest -q` grün.
- Web: `npm run lint`, `npx tsc --noEmit`, `npm test`, `npm run build` grün.
- `security-reviewer` über die OAuth-Änderung gelaufen, Befunde behoben.
- PR (Draft) auf `claude/determined-noether-wi53zd`.

## Anti-Scope
- Kein Subdomain-/Infra-pro-Agent (Option B).
- Kein Token im Connector/Systemprompt.
- Kein MCP-Server-Catch-all (Option C).
