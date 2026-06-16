# ADR-0034 — MCP-Server: Streamable-HTTP-Transport optional, stdio bleibt Default

- Status: Akzeptiert
- Datum: 2026-06-07
- Bezug: ADR-0005 (MCP-API entkoppelt), ADR-0012/0021/0030 (MCP-Tools),
  Followup aus `.claude/plan/2026-05-25-2008_ms2-c3-app-compose.md`
  (Section "MCP-HTTP-Transport") und `deploy/hetzner/README.md`
  (Hinweis "Folge-Task").

## Kontext

Der Who2Be-MCP-Server lief seit MS-2 ausschliesslich ueber **stdio**: der
FastMCP-Default, der den Server als gespawnten Subprozess voraussetzt
(Claude Desktop, Cursor lokal). stdio ist:

- Prozess-lokal — kein Netzwerk-Endpoint, kein Reverse-Proxy, keine Auth-Schicht.
- 1:1 zwischen MCP-Client und Server — nicht multi-user-faehig.
- Voraussetzung "User hat Docker/Python lokal".

Damit fallen weg:
- **Anthropic Custom Connectors** (Claude API, claude.ai Workbench, Plugins):
  akzeptieren ausschliesslich HTTP-MCP.
- **ChatGPT MCP**, **Cursor Remote**, **Cline Web**: HTTP-only.
- **Team-Zugriff** ohne Container-Install: nur via HTTP machbar.

Who2Be positioniert sich als selbst-hostbares B2B-Produkt mit Workspaces,
RBAC und Bearer-Tokens (`/v1/tokens`). Die ganze Auth- und Reverse-Proxy-
Infra (Caddy + TLS auf `api.${DOMAIN}` / `app.${DOMAIN}` /
`supabase.${DOMAIN}`) existiert bereits — eine vierte Sub-Domain
`mcp.${DOMAIN}` ist 1 Caddy-Block.

## Entscheidung

1. **stdio bleibt Default.** `WHO2BE_TRANSPORT=stdio` ist der unveraenderte
   Standard. Bestehende Aufrufmuster (`docker compose run --rm mcp`,
   Claude-Desktop-Config mit lokalem Container) bleiben funktionsfaehig.
2. **HTTP wird per Env-Flag aktiviert.** `WHO2BE_TRANSPORT=http` schaltet
   FastMCPs `streamable-http`-Transport ein und exponiert den Server auf
   `WHO2BE_HTTP_HOST:WHO2BE_HTTP_PORT{WHO2BE_HTTP_PATH}`
   (Defaults: `0.0.0.0:8765/mcp`).
3. **Compose-Trennung in zwei Profile.** `profiles: ["mcp"]` (stdio,
   one-shot, unveraendert) + `profiles: ["mcp-http"]` (long-running,
   depends_on `api:healthy`). Beide nutzen dasselbe Image.
4. **Caddy-Route `mcp.${DOMAIN}`** mit security_headers, harter CSP
   (`default-src 'none'`) und `flush_interval -1` fuer SSE-Streaming.
5. **Auth = bestehender API-Bearer-Token.** Caddy reicht `Authorization`
   unveraendert weiter. Der Server liest den Token aus `WHO2BE_API_TOKEN`
   (server-globale Identity). Per-Request-Auth-Forwarding (Bearer aus
   Request-Headers → API-Client) ist Followup, siehe §Multi-Tenant.
6. **Strukturierte Logs auf `stderr`.** Korrigiert den Stdio-Bug
   (`core_logging.py`: StreamHandler → `sys.stderr`): JSON-Log-Zeilen auf
   stdout korrumpieren MCP-Frames und machten den Server fuer Claude
   Desktop / Cursor unbenutzbar.

## Konsequenzen

### Positive

- **Sofortige Cloud-Faehigkeit.** Claude-Custom-Connector + ChatGPT-MCP
  koennen via `https://mcp.${DOMAIN}/mcp` angebunden werden, sobald
  `--profile mcp-http up` laeuft.
- **Kein Code-Doppelweg.** Ein FastMCP-Server, eine Tool-Registry, zwei
  Transports — verglichen mit "zwei Code-Pfade" minimaler Wartungsaufwand.
- **Stdio-Logging-Bug fixed.** Bestehende stdio-Nutzer (Claude Desktop)
  bekommen erstmals wirklich saubere JSON-RPC-Frames.

### Negative / Tradeoffs

- **Single-Identity in v1.** Der HTTP-Server agiert mit einem festen
  `WHO2BE_API_TOKEN` — alle Calls landen im selben Workspace. Multi-User
  braucht eine zweite Naht (siehe Followup).
- **Healthcheck nutzt Python-urllib** (kein curl im Image). Funktioniert,
  ist aber etwas teurer als ein C-Tool. Lebbar bei 15s-Intervall.

### Multi-Tenant (implementiert, 2026-06-16)

Per-Request-Auth ist jetzt umgesetzt (`server.py` `_request_token`/
`build_client`): im HTTP-Transport bestimmt der eingehende `Authorization:
Bearer`-Header pro Tool-Call den API-Token — jede Session ist ihr eigener,
serverseitig (in der API) gescopter Token/Agent. Der `authorization`-Header
muss explizit via `get_http_headers(include={"authorization"})` angefordert
werden (FastMCP filtert ihn sonst per Default). Fehlt/leer der Bearer im
HTTP-Modus, wird **hart abgelehnt** — kein Rueckfall auf den statischen
`WHO2BE_API_TOKEN` (sonst agierte ein Caller mit kaputtem Header als der
privilegierte Server-Token). stdio nutzt unveraendert den Env-Token. Die
Workspace-Resolution (`/v1/me`) wird pro Token (sha256-Key) mit LRU+TTL
gecacht.

## Verifizierung

- `apps/mcp/tests/test_server_main.py` — `main()` dispatcht korrekt nach Env.
- `apps/mcp/tests/test_logging_stream.py` — `configure_logging` schreibt
  auf `sys.stderr`.
- Lokaler Smoke: `--profile mcp-http up -d --wait` + `tools/list` via
  `curl -H "Accept: text/event-stream" http://localhost:8765/mcp` (oder
  hinter Caddy).
