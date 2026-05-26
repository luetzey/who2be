# Plan: Backend-Followups — F-02-Verifikation + F-09 Pagination

## Context

`docs/security-findings.md` listet zwei offene Backend-Findings:

- **F-02 (High, "Followup → MS-2")** — Rate-Limit-Key liest
  `request.client.host`. Hinter dem Caddy-Reverse-Proxy ist das ohne
  Proxy-Header-Handling die Proxy-IP. Die in C3 fuer den Hetzner-Stack
  gebaute `apps/api/Dockerfile`-CMD setzt bereits
  `--proxy-headers --forwarded-allow-ips *` — uvicorns
  `ProxyHeadersMiddleware` rewriten `request.client.host` aus
  `X-Forwarded-For`. Damit greift `_rate_limit_key` automatisch korrekt.
  Was fehlt: ein **Test**, der das verbindlich macht, plus
  **Doku-Update** von "Followup" auf "Fixed".

- **F-09 (Low, "Followup")** — `GET /v1/personas`, `/v1/playbooks` und
  `/v1/tokens` liefern alle Owner-Zeilen ohne Limit. Akzeptanzkriterium
  aus dem Finding: `?limit` (Default 100, Max 200) + `?cursor`
  (`created_at` + `id`). Owner-internes Problem — kein
  Cross-Owner-Leak, aber DoS-Multiplikator wenn F-01 jemals
  zurueckkippt.

Ziel: beide Findings auf "Fixed", Backend damit security-final fuer
den Hetzner-Cutover; Web-Folgeanpassungen sind explizit separat
(siehe "Out of Scope").

Roadmap-Einordnung: kein neues Milestone — Folgearbeit zu MS-3 H3.
Backup-Restore-Drill (H4) bleibt blockiert durch MS-2 und nicht Teil
dieses Plans.

## Approach

### F-02 — Verifikation

Code-Aenderung minimal: `_rate_limit_key` in
`apps/api/src/who2be_api/core/rate_limit.py:27` arbeitet bereits
korrekt, sobald uvicorn die echte IP in `request.client.host`
schreibt. Die `--proxy-headers`-Aktivierung passiert ausschliesslich
ueber die uvicorn-CLI (Dockerfile / lokale Dev-Args), nicht im
Python-Code — also testen wir genau **die Annahme**, dass die
Key-Funktion die rewritten IP liest.

Zwei Tests:

1. **Unit-Test** auf `_rate_limit_key`: konstruiere zwei Starlette-
   `Request`-Objekte mit unterschiedlichen `scope["client"]`-Tupeln
   und assertiere, dass die Keys differieren (anonymer Pfad). Ein
   dritter Fall mit `Authorization`-Header bleibt unabhaengig von
   der Client-IP.
2. **Integrationstest** (Anti-Regression auf der Boot-Konfiguration):
   ein Test, der die produktive `CMD`-Zeile aus
   `apps/api/Dockerfile` parst und prueft, dass `--proxy-headers`
   sowie `--forwarded-allow-ips` darin enthalten sind. Verhindert,
   dass kuenftiges Image-Refactoring die Mitigation kippt.

Doku: in `docs/security-findings.md` F-02-Status auf **Fixed**,
Tabelle und Detail-Abschnitt anpassen. Die drei in F-02
gelisteten Akzeptanzkriterien sind durch C3-Compose + Caddyfile
bereits erfuellt (`apps/api/Dockerfile:60-69`).

### F-09 — Pagination

**Schema-Entscheidung:** Response-Shape bleibt `list[T]`, der
`next_cursor` wird im **Response-Header** `X-Next-Cursor`
transportiert. Begruendung: kein Breaking Change fuer die Web-UI
(Hook `useListData` bleibt; Anzeige der ersten 100 Items
unveraendert), gleichzeitig schaltet der Header die Pagination
fuer API-Clients frei, die sie nutzen wollen. Wrapper-Models
waeren idiomatischer, koennen in einer spaeteren API-v2-Iteration
nachgezogen werden.

**Keyset statt Offset:** Cursor ist
`base64url(created_at_iso + "|" + id_uuid)`, OFFSET wuerde unter
Insert-Last instabil. SQL aendert sich zu
`WHERE owner_id = $1 AND (created_at, id) < ($2, $3)
 ORDER BY created_at DESC, id DESC LIMIT $4`.

**Limit:** `Annotated[int, Query(ge=1, le=200)] = 100` — Default und
Max wie im Finding gefordert.

**Scope der List-Endpoints:**

| Endpoint                              | Pagination | Begruendung                    |
| ------------------------------------- | ---------- | ------------------------------ |
| `GET /v1/personas`                    | ja         | F-09 Kern                      |
| `GET /v1/playbooks`                   | ja         | F-09 Kern, Filter `tag`/`trigger` bleibt |
| `GET /v1/tokens`                      | ja         | F-09 Kern                      |
| `GET /v1/personas/{id}/versions`      | nein       | scoped auf eine Persona — unter realistischen Versions-Zahlen unkritisch; OOS hier |
| `GET /v1/playbooks/{id}/versions`     | nein       | dito                           |
| `GET /v1/personas/{id}/playbooks`     | nein       | bounded durch `playbook_ids`-Limit (200) aus F-01 |

## File-by-file Changes

### A. `packages/models/src/who2be_models/`

Neuer kleiner Helper fuer Cursor-Codierung, z. B. `pagination.py`:
- `encode_cursor(created_at: datetime, id: UUID) -> str`
- `decode_cursor(raw: str) -> tuple[datetime, UUID] | None`
- `MAX_LIMIT = 200`, `DEFAULT_LIMIT = 100` (Konstanten zur
  Wiederverwendung in Routern + Tests).

Pure Funktionen, keine Pydantic-Models noetig — bewusst klein.

### B. Repositories — Keyset-Queries

- `apps/api/src/who2be_api/repositories/persona_repository.py` —
  `list_by_owner` um `limit: int, after: tuple[datetime, UUID] | None`
  ergaenzen. Bestehende Query aus `_SELECT_CURRENT` plus
  `WHERE`-Klausel erweitern. Tie-Breaker `id` ist Pflicht, damit
  zwei Rows mit gleichem `created_at` stabil sortiert sind.
- `apps/api/src/who2be_api/repositories/playbook_repository.py` —
  gleiche Erweiterung, **zusaetzlich** kompatibel mit den
  existierenden `tag`/`trigger`-Filtern (Filter und Keyset im selben
  `WHERE`-Block, parametriert).
- `apps/api/src/who2be_api/repositories/token_repository.py` —
  `list_by_owner` analog.

Protocol-Definitionen am Kopf der jeweiligen Datei mitziehen.

### C. Services — `next_cursor` berechnen

- `apps/api/src/who2be_api/services/persona_service.py:35` — `list_all`
  bekommt `limit`/`cursor`-Parameter. Wenn das Repository
  `limit + 1` Zeilen zurueckgibt: letzte Zeile wegwerfen, aus ihr
  den `next_cursor` ableiten; sonst `next_cursor = None`. Trick
  spart einen zweiten Roundtrip.
- `playbook_service.py`, `token_service.py` — analog.

### D. Routers — Query-Param + Header

- `apps/api/src/who2be_api/routers/personas.py:35-37` — `list_personas`
  bekommt `limit`/`cursor`-Query-Params und `response: Response`.
  Service-Aufruf liefert Tupel `(items, next_cursor)`; Router setzt
  `response.headers["X-Next-Cursor"]` und gibt `items` zurueck.
- `playbooks.py`, `tokens.py` — analog. Bei `playbooks.py` die
  `tag`/`trigger`-Params unveraendert mitnehmen.

CORS bereits korrekt fuer Custom-Header
(`apps/api/src/who2be_api/main.py:46-47` hat `Authorization,
Content-Type, X-Request-ID` — `X-Next-Cursor` muss in `expose_headers`
ergaenzt werden, damit Browser-Clients ihn lesen koennen).

### E. Tests

- `apps/api/tests/test_personas.py` — Pagination-Cases:
  zwei Pages durchblaettern, Limit-Validation (`?limit=0`, `?limit=201`
  → 422), ungueltiger Cursor (→ 422), Owner-Isolation bleibt unter
  Pagination (Owner B sieht nicht Owner As Items).
- `apps/api/tests/test_playbooks.py` — gleiche Cases plus
  **Filter+Pagination kombiniert** (`?tag=...&limit=2`).
- `apps/api/tests/test_tokens.py` — analog ohne Filter.
- Neu: `apps/api/tests/test_rate_limit_proxy.py` — Unit-Tests fuer
  `_rate_limit_key` mit konstruierten Mock-Requests + ein
  Static-Check auf die Dockerfile-CMD.
- `packages/models/tests/test_pagination.py` — Roundtrip
  encode/decode, Reject-malformed-Cursor.

### F. Doku

- `docs/security-findings.md`:
  - Findings-Tabelle: F-02 → "Fixed", F-09 → "Fixed".
  - F-02-Detail um Verweis auf Test und C3-Dockerfile ergaenzen.
  - F-09-Detail um Verweis auf Header-Schema und Endpoint-Scope.
  - Akzeptanz-Tabelle aktualisieren.
- `docs/architecture.md` — falls Pagination-Schema dort dokumentiert
  werden sollte (kurz pruefen).

## Wiederverwendung

| Quelle                                                               | Nutzung                                                       |
| -------------------------------------------------------------------- | ------------------------------------------------------------- |
| `_SELECT_CURRENT` in `persona_repository.py`                         | Basis fuer Keyset-Query — nur `WHERE` und `LIMIT` anhaengen.  |
| `_escape_like` in `playbook_repository.py`                           | Bleibt fuer Tag/Trigger; orthogonal zur Pagination.           |
| `apps/api/Dockerfile:60` `--proxy-headers --forwarded-allow-ips *`   | F-02-Mitigation, wird durch Test gegen Regression abgesichert.|
| `apps/api/tests/test_personas.py:_auth`, `_prepare_db`, `_cleanup`   | Test-Harness fuer neue Pagination-Cases unveraendert.         |
| `_rate_limit_key` in `core/rate_limit.py:27`                         | Unveraendert — wird nur durch neue Tests umstellt.            |

Nicht wiederverwendet: ein generisches `PagedResult[T]`-Wrapper-Model
— bewusst weggelassen, weil Header-Schema die Web-UI nicht bricht.

## Verifikation

1. **Tests gruen**:
   `uv run pytest -q apps/api/tests/test_personas.py
    apps/api/tests/test_playbooks.py apps/api/tests/test_tokens.py
    apps/api/tests/test_rate_limit_proxy.py
    packages/models/tests/test_pagination.py`
2. **Lint + Typecheck**:
   `uv run ruff check . && uv run ruff format --check .
    && uv run mypy .`
3. **Smoke gegen lokales Compose**:
   `docker compose up -d --wait && scripts/smoke.sh` —
   `/v1/health` weiterhin gruen.
4. **Manuelle Pagination-Probe** (lokal mit gueltigem Token):
   ```
   curl -i -H "Authorization: Bearer $T" \
     "http://localhost:8000/v1/personas?limit=2"
   # `X-Next-Cursor`-Header pruefen, dann mit
   # `?limit=2&cursor=<value>` weiterblaettern.
   ```
5. **F-02-Verhaltenscheck im Hetzner-Stack** (optional, nur falls
   Caddy lokal hoch ist):
   ```
   curl -H "X-Forwarded-For: 9.9.9.9" \
     -i https://api.localhost.test:8080/v1/health
   ```
   und in API-Logs pruefen, dass `client_host=9.9.9.9` erscheint —
   primaerer Beweis bleibt aber der Unit-Test.
6. **CI** (`.github/workflows/ci.yml`) muss ohne Anpassung gruen
   laufen.

## Out of Scope (bewusst)

- **Web-UI Pagination-Controls** — Frontend zeigt weiterhin die
  erste Seite (≤ Default-Limit). Mehrseiten-Navigation,
  Infinite-Scroll oder `useListData`-Erweiterung sind ein separater
  Web-Plan, sobald reale User > 100 Items haben.
- **Pagination fuer Versions-Endpoints** — siehe Scope-Tabelle oben.
- **`PagedResult[T]`-Wrapper-Model / API-v2** — bewusste Migration
  spaeter, dieser Plan haelt v1 kompatibel.
- **Constant-Time-Token-Vergleich (F-04)** — bleibt accepted.
- **Backup-Restore-Drill (MS-3 H4)** — blockiert durch MS-2.
- **Security-Header / CSP (F-12)** — Caddyfile-Sache, nicht Backend.
