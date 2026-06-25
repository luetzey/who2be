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
