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

## Addendum 2026-08-22 (2) — Consent-Preview: den gelockten Agenten lesbar machen

**Problem:** Der Consent lud die Agentenliste nur für `me.default_workspace_id`,
während das autoritative Gate `_resolve_agent_membership` über **alle**
Memberships des Users sucht. Zwei Folgen (Issue #405):

1. Lag der gelockte Agent in einem Nicht-Default-Workspace, fiel die Anzeige auf
   die rohe UUID zurück — der User bestätigte eine Bindung, die er nicht lesen
   kann, ohne jede Angabe des Ziel-Workspace.
2. War der Default-Workspace leer, griff die `agents.length === 0`-Sperre und der
   Consent war gar **nicht durchführbar**, obwohl der Agent existierte und der
   User berechtigt war.

Vor der Pfad-Bindung (Addendum 1) kam der Agent-Hint praktisch nie am Consent an
— der Hard-Lock war ein toter Pfad und die Lücke damit unsichtbar.

**Entscheidung:** `POST /oauth/consent/preview` nimmt denselben HMAC-signierten
Request-Blob und löst den Agenten über **exakt** `_resolve_agent_membership` auf.
Antwort: `{locked: bool, agent: {id, name, workspace_id, workspace_name} | null}`.

Vier Fälle: ungültiger/abgelaufener Blob ⇒ 400; kein Hint ⇒ `{locked: false}`
(Dropdown wie bisher); Hint auflösbar ⇒ Name + Workspace, Approve aktiv; Hint
nicht auflösbar ⇒ `{locked: true, agent: null}`, Approve gesperrt mit Begründung.

**Warum dieser Zuschnitt — drei bewusste Entscheidungen:**

- **Kein Agent-ID-Parameter.** Der Trust-Anker bleibt der signierte Blob. Ein
  Endpunkt, der eine beliebige Agent-UUID auflöst, wäre ein IDOR-Vektor; so
  verrät er ausschließlich, was der eingeloggte User ohnehin gerade autorisieren
  soll.
- **Kein Existenz-Orakel.** „Agent existiert nicht" und „Agent gehört dir nicht"
  laufen durch denselben Rückgabepfad — identischer Status, identischer Body.
  `_resolve_agent_membership` iteriert nur über die eigenen Workspaces, ein Agent
  außerhalb dieser Menge ist schlicht „nicht gefunden"; der Namens-Read passiert
  erst **nach** dem Gate.
- **Kein 403 im Preview.** Der Consent wurde noch nicht abgeschickt — das ist
  eine Anzeige, kein Autorisierungsversuch. Das 403 bleibt am
  `POST /oauth/consent`, wo die Entscheidung tatsächlich fällt.

Verworfen: `GET /v1/me/agents` (legt eine allgemeine workspace-übergreifende
Lesefläche an, wo das Problem einen einzigen, bereits bekannten Agenten
braucht); rein im Frontend über die `MeRead`-Workspaces (dupliziert die
Auflösungslogik im Client — die Anzeige wäre eine Rekonstruktion neben dem
echten Gate statt dessen Antwort).

**Schichtung:** Der Read liegt als `PgOAuthRepository.agent_display` im
Repository, den Mandanten setzt der Service per `tenant_scope` — `tenant_scope`
ist reine ContextVar-Verwaltung, also eine Service-Entscheidung (Muster wie
`gdpr_export_service`). Damit bleibt die Interims-Leitplanke aus `CLAUDE.md`
(kein neues SQL in `services/`) gewahrt; das vorbestehende SQL in
`_resolve_agent_membership` gehört in den späteren ADR-0002-Umzug.

Verifizierung: `test_oauth.py` — alle vier Fälle DB-frei plus ein
Integrationstest; `test_consent_preview_is_no_existence_oracle` vergleicht die
Antworten für „fremd" und „nicht existent" byte-genau.

## Addendum 2026-08-22 (3) — Consent ist ein Menschen-Endpunkt, kein Maschinen-Endpunkt

**Befund (Security-Review zum Preview-Paket, vorbestehend):** `POST /oauth/consent`
akzeptierte auch `w2b_`-API-Tokens. `get_current_principal` bedient JWT **und**
Token-Pfad; `consent()` las ausschliesslich `principal.user_id` und ignorierte
die Token-Pins (`token_workspace_id` / `token_role` / `token_agent_id`). Da
`/oauth/*` ausserhalb von `_WORKSPACE_PREFIX` laeuft, griff auch kein
`get_current_workspace`, das die Pins sonst durchsetzt.

**Wirkung (am Code verifiziert):** `_issue` leitet die Rolle des frischen Tokens
aus `_resolve_agent_membership` ab — der **aktuellen** Membership-Rolle des
Owners, nicht der im aufrufenden Token gepinnten Snapshot-Rolle. Ein bewusst auf
`viewer` herabgestufter PAT, oder ein beim LLM-Client liegender Connector-Token,
konnte damit ueber DCR → `authorize` → `consent` → `token` einen `admin`-Token
praegen; mit einer Agent-UUID aus einem anderen Workspace desselben Owners
zusaetzlich den Workspace- und Tool-Policy-Pin verlassen. Die dabei entstehende
Refresh-Kette traegt `rotated_from = NULL` und ueberlebt ein
`revoke_refresh_chain` auf die Ursprungskette — aus einem 8-Stunden-Token wurde
eine 30-Tage-Kette.

**Entscheidung:** `get_consent_principal` klemmt `POST /oauth/consent` **und**
`POST /oauth/consent/preview` hart auf den JWT-Pfad (401 fuer Token-Aufrufer).
Diskriminator ist `token_workspace_id is None` — laut `CurrentPrincipal`-Vertrag
sind API-Tokens immer workspace-gepinnt.

Die Begruendung ist semantisch, nicht nur technisch: der Consent ist der
interaktive Entscheidungspunkt eines **Menschen** („ja, dieser Client darf als
dieser Agent handeln"). Eine Maschine darf ihn nicht selbst passieren, sonst
laesst sich ein bereits ausgegebener Token dazu benutzen, sich einen neuen,
staerkeren ausstellen zu lassen. `register`, `authorize` und `token` bleiben
unveraendert (anonym bzw. PKCE-geschuetzt, ohne Principal).

`_issue`s Rollen-Herleitung bleibt bewusst wie sie ist — sie ist Teil des
Designs (der Connector-Token traegt die aktuelle Rolle des Consent-Users, nicht
eine eingefrorene). Gefixt ist der **Zugang**, nicht die Ableitung.

**Folgebefund am neuen Preview:** `OAuthConsentApprove.agent_id` ist jetzt
optional. Ablehnen braucht keinen Agenten, und im Hard-Lock-Fall gewinnt ohnehin
der signierte Blob. Als Pflichtfeld scheiterte ein „Ablehnen" auf einer
Consent-Seite ohne aufloesbare Auswahl schon an der Pydantic-Validierung (422) —
der Client bekam nie den `access_denied`-Redirect, der User sah nur einen
generischen Fehler. `approve=true` ganz ohne Agent faellt serverseitig als
`invalid_request`; die Pruefung steht **nach** dem Hard-Lock, damit der Blob auch
dann bindet, wenn der Client gar keinen `agent_id` schickt.

Verifizierung: `test_oauth_consent_rejects_api_token` (schlaegt gegen den alten
Code fehl), dazu die Preview-Variante und die drei `agent_id`-Faelle
(Ablehnen ohne Agent, Zustimmen ohne Agent, Zustimmen ohne Agent mit Blob-Hint).
