# Plan — MCP-Connector: Agent ohne erneute Auswahl binden

_Erstellt: 2026-08-22 13:30 · Branch: `claude/amazing-bardeen-u3gwoj`_

## Symptom (User-Report)

Beim Verbinden eines Remote-MCP-Connectors landet der User im Frontend, loggt
sich ein — und muss dann **erneut den Agenten auswählen**, obwohl er eine
agent-spezifische Connector-URL (`…/mcp?agent=<uuid>`) eingetragen hat.

## Root Cause (aus dem Code belegt)

Der Hard-Lock ist implementiert und funktioniert — er bekommt nur nie einen Hint:

1. Web baut die Connector-URL als `${config.mcpUrl}?agent=${agentId}`
   (`apps/web/src/features/agents/components/AgentConnectorSection.tsx:26`).
2. Der MCP-Server advertised per RFC-9728-PRM die **kanonische** Resource
   `{mcp_public_url}{http_path}` — **ohne Query**
   (`apps/mcp/src/who2be_mcp/auth.py:55` → FastMCP `RemoteAuthProvider`,
   `_get_resource_url` hängt nur den Mount-Pfad an).
3. Der LLM-Client (Claude) benutzt für den RFC-8707-`resource`-Parameter die
   **PRM-Resource**, nicht die eingetragene URL → `?agent=` fällt weg.
4. `_resource_agent_hint(resource, base)` bekommt damit die nackte Basis und
   liefert `None` (`apps/api/src/who2be_api/services/oauth_service.py:396`).
5. Blob trägt `agent_id: null` → `OAuthConsentPage` fällt auf das Dropdown
   zurück (`apps/web/src/features/auth/pages/OAuthConsentPage.tsx:126`).

Belegkette per Ausschluss: Käme die Query mit, gäbe es entweder den Locked-Input
(gültige UUID) oder `400 invalid_target` (ungültige). Der User sieht das
Dropdown ⇒ die Query erreicht `/oauth/authorize` nicht.

Das war im Ursprungs-Plan bereits als Fail-safe notiert
(`.claude/plan/2026-06-25-1324_agent-connector-params.md`, „Schickt Claude die
kanonische PRM-Resource, bleibt alles wie heute“) — genau dieser Fall ist jetzt
der Normalfall.

**Der Login selbst ist nicht der Bug** — ein OAuth-Consent ohne Session ist
zwingend. Zu fixen ist nur die *erneute Agenten-Auswahl*.

## Design-Weiche

Die Query überlebt die Client-Kanonisierung nicht. Der **Pfad** dagegen ist
Teil der Resource-Identität (RFC 8707 verbietet nur das Fragment; RFC 9728
leitet den PRM-Pfad direkt aus dem Resource-Pfad ab).

### Option A — Agent in den Pfad: `…/mcp/a/<uuid>` (Empfehlung)

- **MCP-Server**: PRM-Route `/.well-known/oauth-protected-resource/mcp/a/{id}`
  liefert `resource = {public}/mcp/a/{id}`; ASGI-Rewrite `/mcp/a/{id}` → `/mcp`
  für die eigentlichen MCP-Requests; `WWW-Authenticate` der 401-Antwort zeigt
  auf die agent-spezifische PRM-URL.
- **API**: `_resource_agent_hint` akzeptiert zusätzlich `{base}/a/<uuid>`;
  `?agent=` bleibt als Rückwärtskompatibilität bestehen. Die im Blob
  gespeicherte (kanonische) `resource` und damit die Audience-Kette ändert sich
  **nicht**.
- **Web**: Connector-URL wird `${config.mcpUrl}/a/${agentId}`.
- Pro: löst die Ursache; URL bleibt pro Agent eindeutig; keine Infra pro Agent
  (Caddy proxied `mcp.{$DOMAIN}` bereits pfad-agnostisch); Hard-Lock-Semantik
  und Sicherheits-Gates bleiben unverändert.
- Contra: ~80 LOC neue MCP-Server-Verdrahtung (Routing + PRM + 401-Header);
  bleibt clientabhängig — nur eben von einer Eigenschaft (Pfad), die jeder
  konforme Client erhält, statt von einer, die Claude nachweislich verwirft.

### Option B — Letzte Agent-Wahl je Client merken

- Beim Consent `(user_id, client_id) → agent_id` persistieren und beim nächsten
  Consent desselben Connectors vorbelegen/überspringen.
- Pro: klein, rein in API + Web, kein Protokoll-Eingriff.
- Contra: **behebt den Bug nicht** — die erste Verbindung (genau der beklagte
  Moment) fragt weiterhin. Löst nur Re-Auth nach Refresh-Ablauf.

### Option C — Consent-UX entschärfen

- Auswahl überspringen, wenn der User genau einen Agenten hat; sonst Dropdown
  mit besserem Default/Suche.
- Pro: minimal, sofort.
- Contra: kosmetisch; bei mehreren Agenten (der Regelfall hier) unverändert.

**Empfehlung: Option A.** B und C kurieren Symptome, A entfernt die Ursache.
A und C schließen sich nicht aus — C kann später separat kommen.

## Arbeitspakete (bei Zustimmung zu A)

### WP1 — MCP-Server: agent-Pfad + per-Agent-PRM (sicherheitsrelevant)
`apps/mcp/src/who2be_mcp/agent_path.py` (neu) + `server.py:main`, `auth.py`.
Tests: `apps/mcp/tests/` — PRM-Body korrekt, Rewrite trifft `/mcp`, 401-Header
zeigt auf die agent-PRM, ungültige UUID → 404.

### WP2 — API: Pfad-Variante im Resource-Matching
`apps/api/src/who2be_api/services/oauth_service.py` (`_resource_agent_hint`).
Tests: `apps/api/tests/test_oauth.py` — Pfad-Form, Query-Form (Regression),
Grenzfälle (`/a/` ohne UUID, `/a/<uuid>/x`, fremde Basis) → `invalid_target`.

### WP3 — Web: Connector-URL + Hinweistext
`AgentConnectorSection.tsx`, i18n `de.json`/`en.json`, Komponententest.

### WP4 — Doku
ADR-0036-Ergänzung (Pfad-Variante), `CHANGELOG` (Unreleased),
`.claude/context/STATE.md` + `DECISIONS.md`.

## DoD
- Python: `uv run ruff check .`, `uv run mypy .`, `uv run pytest --cov --cov-fail-under=85`
- Web: `npm run lint`, `npx tsc --noEmit`, `npm run test:coverage`, `npm run build`
- `security-reviewer` über WP1+WP2 gelaufen, Befunde behoben.
- Draft-PR auf `claude/amazing-bardeen-u3gwoj`.

## Anti-Scope
- Kein Wegfall des Logins (OAuth-Consent braucht eine Session).
- Keine Subdomain/Infra pro Agent.
- Keine Änderung an der Audience-/Token-Bindung (Blob bleibt kanonisch).
