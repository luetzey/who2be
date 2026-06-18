# OAuth-Remote-MCP-Connector — lokaler Smoke (beide Editionen)

End-to-End-Test des OAuth-Flows gegen einen **echten** API- + MCP-Prozess —
einmal **On-Prem** (Owner-DB, RLS umgangen) und einmal **Cloud**
(`who2be_app`, `NOBYPASSRLS`, RLS aktiv). Der Cloud-Lauf ist der eigentliche
Lackmustest: nur dort greift Row-Level-Security, also nur dort beweist sich der
RLS-sichere Consent-Pfad (ADR-0036) und die Tabellen-Grants.

## Ausführen

```bash
scripts/oauth_smoke.sh onprem
scripts/oauth_smoke.sh cloud
```

Jeder Lauf ist **hermetisch + nicht-destruktiv**: er startet eine eigene
Wegwerf-Postgres (`who2be-oauth-smoke-db`, Port 5433), migriert sie frisch,
startet API (`:8000`) + MCP-HTTP (`:8766`) via `uv run` und räumt Prozesse +
Container am Ende auf. Die lokale Dev-DB (`docker compose`) bleibt unberührt.

Voraussetzungen: Docker, `uv`. Kein GoTrue nötig — der Consent-JWT wird direkt
mit dem JWT-Secret gemintet (`scripts/oauth_smoke.py`).

Ports überschreibbar, falls etwas kollidiert:
`SMOKE_API_PORT`, `SMOKE_MCP_PORT`, `SMOKE_DB_PORT`. (Default-MCP ist `8766`,
nicht `8765`, damit ein parallel laufender lokaler `mcp-http`-Stack nicht stört.)

## Was geprüft wird

DCR (RFC 7591) → authorize (Open-Redirect-Choke-Point, PKCE-S256) → consent
(RLS-sicherer Agent-Lookup, signierter Blob) → token (PKCE, agent-gebundener
`w2b_`-Access-Token mit `expires_at` + Refresh) → Code-Replay → Refresh-Rotation
(alter Access widerrufen) → `/v1/me`. Danach der Resource-Server: PRM
(`authorization_servers`), 401 + `WWW-Authenticate` ohne Token, Auth-Gate mit
Token.

## Was der Smoke abdeckt, das die Unit-Tests nicht können

`apps/api/tests/test_oauth.py` läuft als **Owner** (TestClient, monkeypatched) —
es kann die Cloud-Edition nicht abbilden. Der Smoke fährt die API als
`who2be_app` und deckt damit RLS-/Grant-Probleme auf, die nur unter
`NOBYPASSRLS` auftreten (z. B. fehlende Tabellen-Grants für die OAuth-Tabellen,
gefixt in Migration 0049).

## Grenzen

Kein echter Claude/ChatGPT-Client (der bräuchte öffentliches HTTPS + Tunnel) und
keine Web-Consent-Seite (der Consent-Schritt läuft als direkter API-Call). Für
die echte Client-UX siehe den Tunnel-Weg (cloudflared/ngrok → Caddy mit
`api.`/`app.`/`mcp.`-Subdomains).
