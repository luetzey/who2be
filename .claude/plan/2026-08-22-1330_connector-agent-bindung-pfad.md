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

---

# Übergabe-Bericht (2026-08-22, vor dem PR)

## (a) Betroffene Software-Elemente

Ermittelt mit `git diff c180801..HEAD --name-only` + ripgrep-Rückwärtssuche über
`apps/` und `packages/` — nicht aus dem Kontextfenster.

**DIREKT** (importiert / ruft auf):

| Symbol | Aufrufer |
| --- | --- |
| `_resource_agent_hint` (API) | `oauth_service.authorize_to_consent_url:160` — einziger Produktiv-Aufrufer |
| `AgentPathMiddleware`, `build_agent_prm_route` (MCP) | `server.main():1691,1703,1719` — nur im `transport == "http"`-Zweig |
| `is_canonical_agent_uuid` / `AGENT_UUID_PATTERN` (models) | `oauth_service:44,433,445`; `agent_path:36,46,52` |
| `is_agent_id`, `agent_resource_url`, `agent_prm_url`, `parse_agent_id` (MCP) | modul-intern + Tests |

**TRANSITIV** (zweite Ebene): `GET /oauth/authorize` (`routers/oauth.py`) über
`authorize_to_consent_url`; `OAuthConsentPage` über den `agent_id`-Wert im
signierten Blob (Code unverändert, nur der Wert kommt jetzt regelmäßig an —
vorher praktisch nie). `who2be_models.__init__` re-exportiert die drei neuen
Symbole; `packages/models` ist Abhängigkeit von API **und** MCP, der Import ist
aber additiv (keine Signatur geändert).

**VERMUTET — ausdrücklich unsicher** (Laufzeit-Verdrahtung, nicht statisch
belegbar):

- Der ASGI-Stack von FastMCP: `AgentPathMiddleware` wird über
  `mcp.run(middleware=[…])` einsortiert, die PRM-Route über die **private**
  Liste `mcp._additional_http_routes`. Beides ist gegen die aktuell installierte
  FastMCP-Version verifiziert (Middleware läuft vor dem Routing, Route wird von
  `create_streamable_http_app` gelesen), aber ein Upgrade kann das brechen —
  fail-open, siehe ADR-Addendum.
- Deployment: `deploy/hetzner/Caddyfile` proxied `mcp.{$DOMAIN}` pfad-agnostisch,
  der neue Well-Known-Pfad ist also ohne Infra-Änderung erreichbar. Nicht gegen
  die laufende Umgebung getestet.
- Bereits eingetragene Connectoren mit `?agent=`-URL: serverseitig weiter
  akzeptiert, aber nicht gegen einen echten Client verifiziert.

Der Diff ist klein, der Radius nicht: `_resource_agent_hint` sitzt im
Authorize-Choke-Point jedes Connector-Logins.

## (b) Rest-Test-Liste

**Diff-Coverage:** Kein CI-Report verfügbar (kein Docker-Daemon → keine DB).
Lokal gemessen: `agent_path.py` **99 %** (einziger Miss: Branch `134->136`),
`agent_uuid.py` **100 %**, der geänderte Bereich in `oauth_service.py`
(Zeilen 396–447) liegt außerhalb der Missing-Ranges. Gesamt-Coverage 62,68 % —
das Gate `--cov-fail-under=85` reißt, aber **vorbestehend**: der unveränderte
Baseline-Stand liegt bei 62,47 %, Ursache sind 445 übersprungene DB-Tests.

**Von keinem ausgeführten Test abgedeckt:**

- `test_oauth_resource_agent_hint_hard_locks` (beide Hint-Formen) — DB-gated,
  hier übersprungen. **Manuell zu prüfen:** dass ein Consent über
  `…/mcp/a/<uuid>` einen Token ausstellt, der an genau diesen Agenten gebunden
  ist, und dass ein fremder Agent mit 403 durchfällt.
- Der reale OAuth-Flow gegen einen echten Claude-Client. **Manuell zu prüfen —
  das ist die eigentliche Annahme dieses Fixes:** ob der Client die
  Pfad-Resource aus der PRM tatsächlich in den `resource`-Parameter übernimmt.
  Tut er es nicht, greift der Fail-safe (Consent zeigt wie bisher das Dropdown),
  aber der Bug wäre nicht behoben.
- `main()` im `http`-Zweig läuft nur gegen ein gemocktes `mcp.run`
  (`test_server_main.py`); ein echter Serverstart ist nicht getestet.

Verhaltens-neutral und deshalb nicht gelistet: Docstring-/Kommentar-Änderungen,
i18n-Strings, die Umstellung von `try/except UUID` auf Vorab-Prüfung (identische
Fehlermeldung und `error`-Code).

## (c) Security-Review

`security-reviewer` über WP1+WP2 gelaufen: **keine kritischen, hohen oder
mittleren Befunde**. Zwei niedrige:

- **N-1** (Alias-UUID-Schreibweisen) — behoben, Commit `43e9005`, selbst
  gegenverifiziert.
- **N-2** (Consent zeigt bei Agent aus Nicht-Default-Workspace nur die rohe
  UUID) — als Issue #405 ausgelagert; der saubere Fix braucht einen neuen
  Lookup-Endpunkt und gehört nicht in einen Bugfix-PR.

Vier Hinweise (Token-Audience RS-seitig nicht erzwungen, private FastMCP-API,
String-Kopplung `MCP_RESOURCE_URL` ↔ PRM, zwei Hint-Formen parallel) stehen im
ADR-0036-Addendum unter „Bekannte Grenzen".
