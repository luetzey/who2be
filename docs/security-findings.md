# Security-Review — MS-3 H3

- Datum: 2026-05-25
- Methodik: `security-reviewer`-Subagent (read-only) ueber Auth, SQL, CORS,
  Input-Validierung, Logging, Rate-Limit, MCP-Adapter und Web-Frontend.
- Scope-Begrenzung: kein Penetrationstest gegen Live-Instanz, kein
  Dependency-CVE-Scan (`npm audit` / `pip-audit` — eigene Task), keine
  Reverse-Proxy-/CSP-Pruefung (gehoert zu MS-2).
- Plan-Referenz: `.claude/plan/2026-05-25-1909_ms3-h3-security-review.md`.

## Zusammenfassung

13 Findings: **2 High, 5 Medium, 4 Low, 2 Info — keine Critical**.
Neun Findings sind in diesem Branch gepatcht (Pydantic-Length-Limits,
JWT-Audience/Issuer/Role-Check, X-Request-ID-Sanitisierung, MCP-Logging,
CORS-Header-Whitelist, JWT_SECRET-Fail-loud, Query-Param-Length-Limit,
Proxy-IP-Rate-Limit-Verifikation, Keyset-Pagination). Die restlichen
vier sind als bewusst akzeptiert (F-04, F-11, F-13) oder
MS-2-Akzeptanzkriterium fuer den Reverse-Proxy (F-12) dokumentiert.

Positiv: SQL durchgaengig parametrisiert, `_escape_like` fuer ILIKE-Trigger,
Composite-FKs in `persona_playbook` als Defense-in-Depth gegen
Cross-Owner-Links, `set_links` als atomare Transaktion mit `FOR UPDATE`,
Token-Klartext nie persistiert und nur einmal an den Client retourniert,
strukturierte JSON-Logs ohne Authorization-Header / Bodies / Token.

## Findings-Tabelle

| ID   | Severity | Bereich           | Titel                                                                  | Status          |
| ---- | -------- | ----------------- | ---------------------------------------------------------------------- | --------------- |
| F-01 | High     | Input-Validierung | Unbeschraenkte String- und Listenfelder in Persona/Playbook/LinkSet    | Fixed           |
| F-02 | High     | Rate-Limit        | `get_remote_address` ignoriert `X-Forwarded-For` hinter Reverse-Proxy  | Fixed           |
| F-03 | Medium   | Auth/JWT          | `verify_aud=False` und kein `iss`-Check                                | Fixed           |
| F-04 | Medium   | Auth/Token        | Token-Hash-Lookup ohne Constant-Time-Vergleich                         | Accepted        |
| F-05 | Medium   | Logging           | `X-Request-ID` unsanitisiert in Log und Response-Header reflektiert    | Fixed           |
| F-06 | Medium   | MCP               | Volle `httpx`-Exception im Log — kann `Authorization`-Header mitfuehren | Fixed           |
| F-07 | Medium   | CORS              | `allow_headers=["*"]` zu permissiv                                     | Fixed           |
| F-08 | Low      | Auth/JWT          | `JWT_SECRET`-Default `""` macht App stillschweigend nicht-funktional   | Fixed           |
| F-09 | Low      | API/Routing       | Keine Pagination-Limits auf `GET /v1/personas`, `/v1/playbooks`        | Fixed           |
| F-10 | Low      | API/Query         | `tag`/`trigger` Query-Parameter ohne `max_length`                      | Fixed           |
| F-11 | Low      | Web/UI            | `VITE_*`-Fallbacks im Production-Build                                 | Accepted        |
| F-12 | Info     | Security-Header   | Fehlende X-Content-Type-Options, X-Frame-Options, Referrer-Policy, CSP | In Arbeit (MS-3 H5) |
| F-13 | Info     | OpenAPI           | `/docs` und `/openapi.json` ohne Auth                                  | Accepted        |

## Detail je Finding

### F-01 — Unbeschraenkte String- und Listenfelder (High, Fixed)

- **Bereich:** `packages/models/src/who2be_models/{persona,playbook,links}.py`
- **Beschreibung:** Bis auf `name` (200 Zeichen) hatten alle user-eingegebenen
  Strings (`description`, `system_prompt`, `body`, `triggers`, `type`) und
  Listen (`traits`, `tags`, `playbook_ids`) keine Obergrenze. FastAPI/Starlette
  begrenzt Request-Bodies nicht per Default.
- **Risiko:** Authentifizierter Owner haette gigantische Payloads schicken
  koennen, die in jsonb persistiert, in jeder Versions-Antwort retourniert und
  in jeder Versions-History eingefroren werden — DoS auf Speicher,
  DB-Storage und Bandbreite. `set_persona_playbooks` mit 100k UUIDs haette
  zusaetzlich die DB belastet.
- **Patch:** `Field(max_length=...)` an allen Content-Feldern,
  `StringConstraints(max_length=...)` an Trait-/Tag-Elementen,
  `max_length=200` auf `PersonaPlaybookLinkSet.playbook_ids`. Konkrete
  Grenzen: description 2 000 Zeichen, system_prompt 20 000, playbook-body
  50 000, triggers 2 000, traits 200, tags 100, je 50 traits/tags, 200
  Playbook-Links.
- **Tests:** `packages/models/tests/test_persona.py`,
  `test_playbook.py`, `test_links.py` (je 3 neue `ValidationError`-Cases).

### F-02 — `get_remote_address` ignoriert `X-Forwarded-For` (High, Fixed)

- **Bereich:** `apps/api/src/who2be_api/core/rate_limit.py:34`,
  `apps/api/Dockerfile:50-54`
- **Beschreibung:** `slowapi.util.get_remote_address` liest `request.client.host`.
  Hinter dem Reverse-Proxy (Caddy auf Hetzner) ist das ohne
  Proxy-Header-Handling die Proxy-IP — alle anonymen Calls landen in
  einem Bucket. Naiver `X-Forwarded-For`-Trust ist Spoofing-Vektor.
- **Patch:** Die produktive `CMD` in `apps/api/Dockerfile` startet
  `uvicorn` mit `--proxy-headers --forwarded-allow-ips *`. `*` ist
  sicher, weil der Container im internen Compose-Netzwerk keinen
  `ports:`-Eintrag hat und nur Caddy ihn erreicht (siehe
  `deploy/hetzner/who2be/docker-compose.yml`). `ProxyHeadersMiddleware`
  rewriten `request.client.host` aus `X-Forwarded-For`, sodass die
  bestehende `_rate_limit_key`-Logik die echte Client-IP bucketet.
- **Tests:** `apps/api/tests/test_rate_limit_proxy.py` —
  `test_anonymous_keys_differ_per_client_host` /
  `test_bearer_token_overrides_client_host` belegen die
  Key-Funktion-Semantik, `test_dockerfile_cmd_enables_proxy_headers`
  schuetzt gegen kuenftiges Image-Refactoring (Anti-Regression auf die
  CMD-Zeile).

### F-03 — JWT: `verify_aud=False`, kein `iss`-Check (Medium, Fixed)

- **Bereich:** `apps/api/src/who2be_api/core/security.py`
- **Beschreibung:** `jwt.decode` akzeptierte jedes mit demselben Secret
  signierte HS256-Token. `service_role`-Tokens (Supabase-Admin) waeren als
  regulaerer Owner durchgegangen, und ein zweiter Service, der zufaellig das
  gleiche Secret nutzt, haette die API ebenfalls authentifizieren koennen.
- **Patch:** Decode mit `audience="authenticated"`, optionalem `issuer`
  (abgeleitet aus `supabase_url`, leer = keine Pruefung fuer Dev),
  `require=["exp","sub","aud"]`, plus explizite Role-Whitelist
  (`authenticated`). `service_role` und andere Rollen werden 401.
- **Tests:** Fuenf neue `test_security.py`-Faelle (without_aud, wrong_audience,
  service_role, authenticated_role, issuer_when_configured). Alle
  bestehenden JWT-Encodes in den Integrations-Tests erweitert um
  `aud`/`role`.

### F-04 — Token-Hash-Lookup ohne Constant-Time-Vergleich (Medium, Accepted)

- **Bereich:** `apps/api/src/who2be_api/repositories/token_repository.py:54-61`,
  `core/security.py:74-87`
- **Beschreibung:** `WHERE token_hash = $1` und das nachgelagerte
  `touch_last_used` haben unterschiedliche Latenz fuer Treffer vs. Miss.
- **Risiko:** Theoretischer Timing-Side-Channel auf einen **Hash** — kein
  Klartext-Leak. Token sind 256 Bit Entropie, ein praktischer
  Praeimage-Angriff auf SHA-256 ist nicht moeglich; das Timing-Signal
  wuerde maximal die Existenz eines Hash-Werts verraten, dem ohnehin der
  Klartext fehlt.
- **Status:** Bewusst akzeptiert — siehe **ADR-0008** mit explizitem
  Re-Evaluation-Trigger (Multi-User, anhaltend > 1 RPS Token-Auth pro
  Owner, oder Public-Internet-Exposure ohne Caddy). Trigger 2 wird
  ueber `who2be_auth_token_attempts_total` (Prometheus, ADR-0010)
  messbar.

### F-05 — `X-Request-ID` unsanitisiert reflektiert und geloggt (Medium, Fixed)

- **Bereich:** `apps/api/src/who2be_api/core/middleware.py:41-48`
- **Beschreibung:** Eingehender Header wurde unveraendert in
  `structlog.contextvars` gebunden und im Response-Header ausgegeben.
  Latin-1-Decode laesst Steuerzeichen (CR/LF) und beliebige Laenge durch;
  unter `console`-Renderer waere ein Newline als sichtbare Log-Zeile
  durchgegangen, und jeder Log-Record haette beliebig grosse Strings
  gemerged.
- **Patch:** Regex `^[A-Za-z0-9._-]{1,64}$` als Whitelist; ungueltige
  Eingaben werden verworfen und durch ein generiertes UUID-Hex ersetzt.
- **Tests:** `test_logging.py` — Newline-Injection und
  Overlong-Header werden mit generierter ID beantwortet.

### F-06 — MCP-Client logt volle `httpx`-Exception (Medium, Fixed)

- **Bereich:** `apps/mcp/src/who2be_mcp/client.py:48-51`
- **Beschreibung:** `logger.warning("...: %s", exc)` fuer `httpx.HTTPError`.
  `str(exc)` kann das Request-Objekt mit `Authorization`-Header mitfuehren
  — Token-Klartext im Log waere ein Leak.
- **Patch:** Nur `type(exc).__name__` loggen.
- **Tests:** `apps/mcp/tests/test_client.py` —
  `test_network_error_log_does_not_leak_token` capture'd Logs und assertet,
  dass weder `tok` noch `Bearer` darin auftauchen.

### F-07 — CORS: `allow_headers=["*"]` (Medium, Fixed)

- **Bereich:** `apps/api/src/who2be_api/main.py:43-49`
- **Beschreibung:** Wildcard-Header laesst jeden Custom-Header durch die
  Preflight. `allow_credentials=False` mildert das, ist aber kein expliziter
  Whitelist-Vertrag.
- **Patch:** `allow_headers=["Authorization","Content-Type","X-Request-ID"]`
  und `allow_methods=["GET","POST","PUT","DELETE","OPTIONS"]`.
- **Tests:** `apps/api/tests/test_cors.py` —
  `test_preflight_rejects_disallowed_custom_header` beweist, dass
  `x-not-allowed` nicht mehr im `Access-Control-Allow-Headers` der Antwort
  erscheint.

### F-08 — `JWT_SECRET`-Default `""` (Low, Fixed)

- **Bereich:** `apps/api/src/who2be_api/core/db.py:71-85`
- **Beschreibung:** Bisher nur Warning bei zu kurzem/leerem Secret — App
  startete stillschweigend in einem Auth-deaktivierten Zustand.
- **Patch:** Pragmatische Mitte: nicht-leerer aber zu kurzer Secret
  (`0 < len < 32`) raised `RuntimeError` im Lifespan (sofortiger Boot-Crash);
  leerer Secret bleibt eine Warning (Dev-Mode mit nur API-Tokens). So
  faengt der haeufige Konfig-Fehler "Secret zu kurz" loud, ohne die
  Test-/Dev-Workflows zu brechen, die bewusst ohne Supabase-JWT arbeiten.
- **Tests:** `apps/api/tests/test_db.py` —
  `test_lifespan_fails_loud_on_short_jwt_secret` und unveraenderter
  `test_lifespan_warns_on_empty_jwt_secret`.

### F-09 — Keine Pagination-Limits (Low, Fixed)

- **Bereich:** `apps/api/src/who2be_api/routers/{personas,playbooks,tokens}.py`
- **Beschreibung:** `list_*`-Endpunkte lieferten ohne Limit alle Zeilen
  des Owners. Owner-internes Problem (kein Cross-Owner-Leak); kombiniert
  mit F-01 (gefixt) waere ein Multiplikator gewesen.
- **Patch:** Keyset-Pagination ueber `(created_at, id)` auf
  `/v1/personas`, `/v1/playbooks`, `/v1/tokens`. `?limit` ist
  `Query(ge=1, le=200)` mit Default 100, `?cursor` ist ein base64url-
  codierter `(iso_timestamp|uuid)`-String. Der Cursor wird per
  Response-Header `X-Next-Cursor` transportiert — Response-Shape bleibt
  `list[T]`, sodass die Web-UI ohne Aenderung weiterlaeuft. SQL nutzt
  `(created_at, id) < ($cursor)` plus Tie-Breaker `id DESC`, damit
  Microsekunden-Kollisionen stabil sortieren. `limit + 1`-Peek im
  Service spart einen zweiten DB-Roundtrip fuer die "hat-mehr?"-Frage.
  Cursor-Helper liegt in `packages/models/src/who2be_models/pagination.py`
  (geteilt mit MCP); Router-Dependency in
  `apps/api/src/who2be_api/core/pagination.py`. CORS expose-Header
  ergaenzt um `X-Next-Cursor`.
  Versions-Endpoints und `/personas/{id}/playbooks` sind bewusst nicht
  paginiert: scoped auf ein Aggregat und bereits durch F-01-Limits
  (200 Playbook-Links) bounded.
- **Tests:** `packages/models/tests/test_pagination.py` (Cursor-
  Roundtrip + malformed → None), `apps/api/tests/test_rate_limit_proxy.py`
  fuer F-02, sowie die Pagination-Cases in `test_personas.py`,
  `test_playbooks.py` (mit Tag-Filter kombiniert), `test_tokens.py`
  (Limit-Validation 0/201 → 422, Cursor `!!!` → 422, Mehrseiten-
  Konsistenz, Owner-Isolation).

### F-10 — Query-Parameter ohne Length-Limit (Low, Fixed)

- **Bereich:** `apps/api/src/who2be_api/routers/playbooks.py`
- **Beschreibung:** `tag` und `trigger` aus dem Query-String gingen
  unbegrenzt in die Repository-Query (Trigger landet in einem ILIKE).
- **Patch:** `Annotated[str | None, Query(max_length=100|200)]`.

### F-11 — `VITE_*`-Fallbacks (Low, Accepted)

- **Bereich:** `apps/web/src/config.ts:14-23`
- **Beschreibung:** Code wirft im `PROD`-Branch, wenn Pflicht-Env leer ist;
  Dev-Fallbacks sind unbedenklich (anon-Key ist per Definition public).
- **Status:** Keine Aktion — die Logik ist defensiv und korrekt.

### F-12 — Fehlende Security-Header (Info, In Arbeit / MS-3 H5)

- **Bereich:** Reverse-Proxy (Caddy, `deploy/hetzner/Caddyfile`)
- **Status:** Aktive Task **MS-3 H5** (Plan-Review 2026-05-26). Konkret
  im Caddyfile zu setzen: `Strict-Transport-Security` (HSTS, via Caddy-
  Auto-HTTPS), `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, restriktive
  CSP fuer `app.<domain>`. Zusaetzlich Pfad-Block `/v1/internal/*` → 403
  (ADR-0010). Vertrag: `deploy/hetzner/tests/test_headers.sh` als
  Smoke. F-13 (`/docs` public) wird im selben Pass per Env-Toggle
  `WHO2BE_DOCS_PUBLIC=false` adressiert.

### F-13 — `/docs` und `/openapi.json` oeffentlich (Info, Accepted)

- **Bereich:** `apps/api/src/who2be_api/main.py:37`
- **Status:** Bewusste Entscheidung fuer ein OSS-Projekt — kein Datenleak,
  nur Surface-Bekanntheit. Falls in Prod doch zu schliessen: `FastAPI(...,
  docs_url=None, redoc_url=None, openapi_url=None)`.

## Akzeptanz

| Block            | Status                                                                     |
| ---------------- | -------------------------------------------------------------------------- |
| Patches gemerged | F-01/03/05/06/07/08/10 in PR aus MS-3 H3; F-02/F-09 in diesem Branch.      |
| Followups        | F-12 (Security-Header / CSP) ist als MS-3 **H5** im Plan-Review v2 verortet. |
| Akzeptiert       | F-04, F-11, F-13 sind ohne weitere Aktion abgenommen (Rationale s. o.).    |
| User-Sign-Off    | Pending — bei Merge dieses PRs als implizit abgenommen.                    |

MS-3 H3 ist damit umgesetzt; offen bleibt H4 (Backup-Restore-Drill, blockiert
durch MS-2).
