# ADR-0036 — OAuth-2.1-Authorization-Server für Remote-MCP-Connector

- Status: Akzeptiert
- Datum: 2026-06-16
- Bezug: ADR-0034 (MCP-HTTP-Transport + Per-Request-Bearer, dies ist die
  Folge), ADR-0023 (Token-Rollen-Snapshot), ADR-0005 (MCP-API entkoppelt).
  Plan: `.claude/plans/lazy-giggling-turtle.md`.

## Kontext

Nach ADR-0034 spricht der MCP-Server Streamable-HTTP und authentifiziert jeden
Request per agent-gebundenem `w2b_`-Bearer. Den Token muss der Nutzer aber
weiterhin **manuell** in eine Client-Config kopieren (+ `mcp-remote`/Node für
stdio-only-Clients). Für nicht-technische Endnutzer zu sperrig.

Der niedrigschwellige Weg, den Claude (Custom Connector) und ChatGPT (MCP)
nativ unterstützen, ist ein **Remote-MCP-Connector mit OAuth-Login**: Nutzer
fügt eine MCP-URL hinzu, loggt sich bei Who2Be ein, **wählt einen Agenten** und
autorisiert — kein Token, keine Datei. Die MCP-Authorization-Spec verlangt dafür
einen OAuth-2.1-Authorization-Server (RFC 9728 PRM, RFC 8414 AS-Metadata,
RFC 7591 DCR, RFC 8707 Resource Indicators, PKCE S256).

## Entscheidung

1. **Who2Be wird selbst zum Authorization Server.** Kein Extra-Dienst: die API
   (`apps/api`) exponiert `/oauth/*` + `/.well-known/oauth-authorization-server`.
   Der MCP-Server (`apps/mcp`) ist der Resource Server (FastMCP
   `RemoteAuthProvider` → PRM + 401/`WWW-Authenticate`). Consent-UI in `apps/web`
   (`/oauth/consent`). Gilt für On-Prem **und** Cloud identisch.
2. **Access-Token = bestehender agent-gebundener `w2b_`-Token** mit gesetztem
   `expires_at` (Migration 0049). Maximale Wiederverwendung — der RS validiert
   ihn wie jeden Bearer via `GET /v1/me`. Refresh-Tokens rotieren (RFC-6749-§10.4,
   Replay → ganze Rotationskette widerrufen).
3. **Ein Connector = ein Agent.** Der Consent zeigt die Agenten des Users; der
   Token erbt Read-Scope + Tool-Policy genau dieses Agenten. Mehrere Agenten =
   mehrere benannte Connectoren (kein Sammel-Token — würde das Scoping aushebeln).
4. **DCR statt CIMD** im MVP (RFC 7591, breite Client-Unterstützung); public
   client (`token_endpoint_auth_method=none`, PKCE als einziger Code-Schutz).
5. **Token-Mint umgeht `TokenService.create`** (das `require_role(editor)` +
   `_deny_agent_bound` erzwingt) und nutzt die Primitive direkt
   (`new_token`/`hash_token`/`TokenRepository.insert`); Autorisierung +
   Owner-Scoping bleiben im `oauth_service`.

## Sicherheit (Security-Review durchgeführt, Pflicht bei Auth-Code)

Abgedeckt: Open-Redirect-Choke-Point (exakte `redirect_uri`-Whitelist, bei
Mismatch 400 **ohne** Redirect), Code-Single-Use (atomar `UPDATE … WHERE
consumed_at IS NULL`, 60 s TTL, nur sha256-Hash), PKCE-S256-Zwang +
konstantzeitlicher Verifier-Vergleich, signierter HMAC-Request-Blob
(Tamper-Schutz Web↔Backend, `hmac.compare_digest`, exp), Confused-Deputy/IDOR
(Consent bindet an eingeloggten User + Membership-Check; **`agent` ist
RLS-isoliert**, daher Auflösung edition-agnostisch über `tenant_scope` je
eigener Workspace), RFC-8707-`resource`-Validierung (authorize **und** consent),
Refresh-Rotation inkl. Chain-Replay-Revoke, Membership-Re-Check beim Refresh
(de-provisionierter User verliert Zugriff, Rolle wird frisch aufgelöst),
Access-Token-Expiry im Auth-Lookup, Rate-Limit auf `register`/`authorize`/
`consent`/`token`, `redirect_uris`-Cap, Consent-Screen zeigt die signierte
`redirect_uri` (nicht den frei wählbaren `client_name`) als Vertrauensanker.

Bewusst offen (akzeptierte Tradeoffs):

- **Kein TTL-Cleanup** für `oauth_client`/`oauth_authorization_code`/
  `oauth_refresh_token` — Folge-Task (Cron/Job). Chains sind durch die
  30-Tage-Refresh-TTL praktisch begrenzt.
- **Keine harte Audience-Trennung zur Use-Zeit:** der Access-Token *ist* ein
  normaler `w2b_`-API-Token; jeder gültige API-Token gilt damit auch am MCP-RS.
  By-design (max. Wiederverwendung) — die `resource`-Validierung wirkt zur
  Issue-Zeit, nicht zur Use-Zeit.
- **MFA/aal2-Gate auf dem Consent = Phase 2** (MVP: aal1-Session genügt).
- **CIMD + SSRF-Härtung der DCR = Phase 2.**

## Konsequenzen

### Positive

- Endnutzer verbinden Claude/ChatGPT per „URL + Login + Agent wählen", ohne
  Token-Copy-Paste oder lokalen Node/Container.
- Ein Codebase, On-Prem = Cloud; keine neue Caddy-Route nötig (PRM unter
  `mcp.${DOMAIN}`, AS-Pfade unter `api.${DOMAIN}`).
- Agent-Scoping + Tool-Policy + RBAC-Snapshot bleiben die Autorisierungsgrenze.

### Negative / Tradeoffs

- Neuer auth-kritischer Oberflächen-Block (vier `/oauth/*`-Endpunkte +
  Metadaten) — entsprechend reviewt + getestet.
- Drei neue Tabellen + `api_token.expires_at`; Cleanup-Job steht aus (s. o.).

## Verifizierung

- `apps/api/tests/test_oauth.py` — voller Flow (DCR → authorize → consent →
  token) + Open-Redirect-/PKCE-/Code-Replay-/Refresh-Rotation-/Expiry-/
  Non-Member-/De-Provision-Invarianten (DB-gated).
- `apps/mcp/tests/test_auth.py` — `Who2BeTokenVerifier` (200→AccessToken,
  401/leer/unerreichbar→None), PRM-`authorization_servers`.
- `apps/web/.../OAuthConsentPage.test.tsx` — Agent-Picker, Approve/Deny-Posts,
  Login-Redirect ohne Session, fehlender Request.
- Offen: **E2E mit echtem Claude/ChatGPT-Client** gegen einen Stack mit
  `api.`/`app.`/`mcp.`-Subdomains (Plan-Schlussschritt).

## Addendum 2026-06-25 — Per-Agent-Connector-URL (`?agent=<uuid>`)

**Problem:** Claude dedupliziert Connectoren nach URL-String; mehrere Agenten an
EINER MCP-URL (`…/mcp`) lassen sich nicht als getrennte Connectoren anlegen
(„A server with this URL already exists"). Der Agent wurde bisher nur im
Consent-Dropdown gewählt.

**Entscheidung:** Die Connector-URL darf `…/mcp?agent=<uuid>` tragen. `authorize`
akzeptiert die `resource` jetzt als kanonische Basis (`mcp_resource_url`) **oder**
Basis + genau einem `?agent=<uuid>` (`_resource_agent_hint`). In den signierten
Request-Blob wandert weiterhin die **kanonische** Resource (ohne Query) — die
RFC-8707-Audience-Kette bleibt an den MCP-Server gebunden; der Agent-Hint reist
getrennt. Trägt der Blob einen Hint, **sperrt** der Consent genau diesen Agenten
(Hard-Lock); der client-gesendete `agent_id` wird ignoriert (Trust-Anker =
HMAC-signierter Blob). Das autoritative Gate bleibt `_resolve_agent_membership`
unter `tenant_scope` — ein fremder Agent fällt mit 403 durch.

**Fail-safe:** Schickt der Client die kanonische PRM-Resource ohne Query, gilt
unverändert die Consent-Auswahl — nichts bricht. Bewusst **kein** Subdomain-/
Pfad-pro-Agent (Infra-Overhead) und **kein** Token im Connector. Die UI zeigt die
fertige Per-Agent-URL auf der Agent-Detail-Seite (`AgentConnectorSection`).

Verifizierung: `test_oauth.py::test_resource_agent_hint_parses_and_validates`
(DB-frei, Grammatik) + `…::test_oauth_resource_agent_hint_hard_locks` (DB-gated,
Hard-Lock + invalid-UUID-Reject). E2E gegen echten Claude-Client weiter offen.

## Addendum 2026-08-22 — Agent-Bindung wandert in den Pfad (`…/mcp/a/<uuid>`)

**Problem:** Das Addendum von 2026-06-25 setzte auf `…/mcp?agent=<uuid>` und
nannte als Fail-safe: „Schickt der Client die kanonische PRM-Resource ohne
Query, gilt unverändert die Consent-Auswahl." Genau das ist der Normalfall —
nicht die Ausnahme. Der LLM-Client übernimmt den RFC-8707-`resource`-Parameter
aus der RFC-9728-Protected-Resource-Metadata des MCP-Servers, und die trägt
`{mcp_public_url}{http_path}` **ohne** Query (FastMCP
`RemoteAuthProvider._get_resource_url`). Der Agent-Hint erreichte `authorize`
also nie; der Hard-Lock war ein toter Pfad und der User musste den Agenten im
Consent erneut wählen (Issue #404).

**Entscheidung:** Der Agent wandert in den **Pfad**. RFC 8707 verbietet nur das
Fragment, und RFC 9728 §3.1 leitet den PRM-Pfad aus dem Resource-Pfad ab — der
Pfad ist damit Teil der Resource-Identität und übersteht die Kanonisierung des
Clients. Die Connector-URL ist `{mcp_public_url}{http_path}/a/<uuid>`.

- **MCP-Server** (`apps/mcp/src/who2be_mcp/agent_path.py`): eine eigene
  PRM-Route unter `/.well-known/oauth-protected-resource{http_path}/a/{id}`
  advertisiert `resource = {public}{http_path}/a/{id}`. `AgentPathMiddleware`
  läuft vor dem Routing, schreibt den Pfad auf den kanonischen Endpoint um
  (damit die bestehende, auth-geschützte Route greift) und korrigiert auf dem
  Rückweg genau einen Wert: den `resource_metadata`-Parameter im
  `WWW-Authenticate` einer 401 — FastMCP setzt dort fest die kanonische PRM-URL.
- **API** (`_resource_agent_hint`): akzeptiert `{base}`, `{base}?agent=<uuid>`
  (Legacy) und `{base}/a/<uuid>`. Pfad-Hint und Query zusammen sind
  widersprüchlich und werden abgelehnt.
- **Unverändert:** In den signierten Blob geht weiterhin die **kanonische**
  Resource; `consent()` vergleicht dagegen. Der Hard-Lock nimmt den Agenten aus
  dem Blob, nicht aus dem Web-Submit. Autoritatives Gate bleibt
  `_resolve_agent_membership` unter `tenant_scope`.

**Kanonische UUID-Form (Security-Review N-1):** Eine Resource-URL *ist* die
Resource-Identität, also muss für dieselbe UUID auf beiden Seiten dieselbe
Strenge gelten. `uuid.UUID()` akzeptiert zusätzlich `{…}`, `urn:uuid:…` und
Formen ohne Bindestriche — das ergäbe mehrere Connector-Identitäten für einen
Agenten. Das Muster liegt deshalb einmal in `who2be_models.agent_uuid`; API und
MCP-Server ziehen es von dort, beide Hint-Formen prüfen es vor `UUID(…)`.

**Bekannte Grenzen (aus dem Security-Review, bewusst offen):**

- Der Resource-Server erzwingt die neue Per-Agent-Audience **nicht**:
  `Who2BeTokenVerifier` prüft nur `GET /v1/me`, die Pfad-UUID wird nach dem
  Rewrite verworfen. Ein Token für `…/a/A` funktioniert auch auf `…/a/B`. Heute
  folgenlos — die effektive Identität kommt ausschließlich aus dem Token —, aber
  die Resource-Granularität suggeriert eine Trennung, die RS-seitig nicht
  existiert.
- Die PRM-Route wird über `mcp._additional_http_routes` registriert: FastMCP hat
  keinen öffentlichen Hook für fertige Starlette-Routes (`custom_route` nimmt nur
  Handler-Funktionen und kann das ASGI-CORS des SDK nicht tragen). Fällt das
  Attribut bei einem Upgrade weg, verschwindet die agent-spezifische PRM **still**
  — fail-open in Richtung „mehr Nutzerinteraktion", also unkritisch, aber
  unsichtbar. Ein Startup-Assert bzw. Smoke-Test würde den Bruch zeigen.
- `MCP_RESOURCE_URL` (API) und die vom MCP-Server advertisierte Resource werden
  byte-genau verglichen; jede Abweichung (Trailing-Slash, Host-Groß-/
  Kleinschreibung, expliziter `:443`) ergibt `invalid_target` — fail-closed, aber
  schwer zu diagnostizieren.
- Die Legacy-Query bleibt vorerst parallel bestehen. Nach dem Migrationsfenster
  sollte sie entfallen, damit ein Agent genau eine Resource-Identität hat.
- Der Consent zeigt bei einem gelockten Agenten aus einem Nicht-Default-Workspace
  nur die rohe UUID (Issue #405) — durch diese Änderung wird der Hard-Lock erstmals
  regelmäßig durchlaufen und die Lücke damit sichtbar.

Verifizierung: `apps/mcp/tests/test_agent_path.py` (Parser, Middleware,
401-Header-Rewrite, PRM-Route, End-to-End gegen eine echte `mcp.http_app`
inkl. Rückwärtskompatibilität des kanonischen Pfads),
`test_oauth.py::test_resource_agent_hint_parses_path_form` (DB-frei) +
`…::test_oauth_resource_agent_hint_hard_locks` (DB-gated, beide Hint-Formen).
E2E gegen echten Claude-Client weiter offen.
