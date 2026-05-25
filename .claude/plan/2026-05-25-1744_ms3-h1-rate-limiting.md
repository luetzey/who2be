# Plan: MS-3 H1 — Rate-Limiting (slowapi) lokal umsetzen

## Context

Stand: MS-1 (Web-UI) ist gemergt, MS-2 (Hetzner-Deploy) wird bewusst aufgeschoben — Weiterentwicklung soll lokal stattfinden. Aus dem MS-3-Hardening-Block ist **H1 Rate-Limiting** der natuerliche erste Schritt (Roadmap-Order, keine Vorgaenger, klar abgegrenzt, kein UI-Aufwand). Ziel: Bevor wir spaeter cloud-deployen, sollen Schreib-/Auth-Routen gegen Brute-Force + Misuse abgesichert sein. Erfolgs-Outcome aus `2026-05-24_who2be-mvp-roadmap.md`:

> `POST /v1/tokens`, `POST /v1/personas`, `POST /v1/playbooks`, `PUT /v1/personas/{id}`, `PUT /v1/playbooks/{id}` sind auf 30/min pro `owner_id` (bzw. IP fuer Pre-Auth) limitiert. Integrationstest belegt 429 nach Ueberschreitung.

Es gibt kein separates Login-Token-Exchange-Endpoint im Code — `POST /v1/tokens` ist der naechste Aequivalent (Supabase-JWT → `w2b_`-Token).

## Approach

`slowapi` als Library (FastAPI-De-facto-Standard, Starlette-kompatibel, In-Memory-Backend ausreichend fuer Single-Process-API). Pro-Endpoint-Dekorator + zentraler Limiter mit eigenem Key-Func, der den Bearer-Token-Hash als Key nutzt (= per-Token-Bucket, faktisch per-Owner) und auf Client-IP zurueckfaellt, wenn kein Auth-Header anliegt. Limit kommt aus `Settings`, damit Tests es ueber Env auf einen niedrigen Wert druecken koennen.

Kein Redis, keine verteilte Storage — bewusst, da Single-Container. Wenn MS-2 spaeter mehrere API-Replicas faehrt, ist das ein klar dokumentiertes Folge-Upgrade (Hinweis in ADR/Code-Kommentar).

## File-by-file Changes

### 1. `apps/api/pyproject.toml` — Abhaengigkeit
Ergaenze in `dependencies`:

```toml
"slowapi>=0.1.9",
```

Danach `uv sync` (User-Aktion zur Verifikation).

### 2. `apps/api/src/who2be_api/core/config.py` — Limit-Setting
Neues Feld in `Settings` (nach Z. 30–53):

```python
rate_limit_write: str = "30/minute"
```

Begruendung-Kommentar (1 Zeile): "Pro Token-Hash bzw. IP. Pro Endpoint via Callable, damit Tests via Env senken koennen."

### 3. `apps/api/src/who2be_api/core/rate_limit.py` — NEU
Inhalt:
- `_rate_limit_key(request)`: liest `Authorization`-Header; wenn Bearer da, `sha256(token).hexdigest()[:32]`; sonst `slowapi.util.get_remote_address(request)`. Deckt beide Auth-Wege (Supabase-JWT und `w2b_`) ohne DB-Roundtrip.
- `_write_limit_value() -> str`: `return get_settings().rate_limit_write` — Callable, damit Settings-Override pro Test wirkt (slowapi unterstuetzt Callables in `limiter.limit(...)`).
- `limiter = Limiter(key_func=_rate_limit_key)` (Modul-Level Singleton).
- Re-Export von `RateLimitExceeded` aus `slowapi.errors` und `_rate_limit_exceeded_handler` aus `slowapi` (zur Vermeidung doppelter Imports in `main.py`).

### 4. `apps/api/src/who2be_api/main.py` — Wiring
- Import `limiter`, `RateLimitExceeded`, `_rate_limit_exceeded_handler` aus `core.rate_limit`; `SlowAPIMiddleware` aus `slowapi.middleware`.
- Nach `FastAPI(...)`-Konstruktion (Z. 17):
  ```python
  app.state.limiter = limiter
  app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
  app.add_middleware(SlowAPIMiddleware)
  ```
- Reihenfolge: `SlowAPIMiddleware` **nach** `CORSMiddleware` registrieren — Starlette wickelt LIFO ab, dann ist CORS aussen und Preflight-OPTIONS wird nicht limitiert.

### 5. Router-Patches (5 Endpoints)
Pro betroffenem Endpoint:
- Signatur um `request: Request` ergaenzen (slowapi-Pflicht: erstes Argument muss `Request` heissen).
- `@limiter.limit(_write_limit_value)` ueber den Endpoint.

Konkret:
- `apps/api/src/who2be_api/routers/tokens.py` → `create_token` (Z. 27)
- `apps/api/src/who2be_api/routers/personas.py` → `create_persona` (Z. 39), `update_persona` (Z. 50+)
- `apps/api/src/who2be_api/routers/playbooks.py` → `create_playbook` (Z. 44), `update_playbook` (Z. 55+)

GET- und DELETE-Endpoints bewusst unangetastet (Roadmap-Scope).

### 6. `apps/api/tests/test_rate_limit.py` — NEU
Pattern an `test_tokens.py` orientiert (TestClient + monkeypatch + `_db_reachable`-Skip-Logik). Test-Cases:
- `test_post_personas_returns_429_after_limit`: monkeypatcht `get_settings` → `Settings(rate_limit_write="2/minute", jwt_secret=_TEST_SECRET)`; setzt Limiter-Storage zurueck; feuert 3× `POST /v1/personas` mit gueltigem JWT; erwartet `[201, 201, 429]`.
- `test_get_personas_not_rate_limited`: 5× `GET /v1/personas` → alle 200 (oder 401 ohne Auth), nie 429.
- `test_rate_limit_keyed_per_token`: zwei verschiedene JWTs (zwei `owner_id`s) koennen unabhaengig je 2 Requests fahren, ohne sich gegenseitig zu blocken.

Wichtig: Limiter-State zwischen Tests zuruecksetzen — Fixture `autouse=True` mit `yield` + `limiter.reset()` am Teardown, sonst leckt State zwischen Tests.

### 7. `docs/architecture.md` — kurze Note
Ein-Absatz-Note unter §Cross-Cutting: "Rate-Limiting via slowapi, In-Memory, Key = Token-Hash oder IP. Single-Process-Annahme; Multi-Replica braucht Redis-Backend." ADR optional als `docs/adr/0007-rate-limiting.md`, falls schon eine ADR-Reihe existiert — sonst weglassen und erst in H2/H3 gebuendelt nachziehen.

## Wiederverwendung (nicht neu erfinden)

- `hash_token()` aus `apps/api/src/who2be_api/core/security.py:35` ist Vorlage fuer den SHA-Key — neu schreiben in `rate_limit.py` als 4-Zeiler (kein Import, um Zyklen zu vermeiden).
- `get_settings()` aus `apps/api/src/who2be_api/core/config.py:56-58` ist die Quelle fuer das Limit.
- Test-Setup-Pattern (`_db_reachable`, `_prepare_db`, `_cleanup`, `monkeypatch.setattr(security, "get_settings", ...)`) aus `apps/api/tests/test_tokens.py:25-67` 1:1 uebernehmen.

## Verifikation

Lokal in dieser Reihenfolge:

1. **Dependency-Install**: `uv sync` — `slowapi` muss in `uv.lock` landen.
2. **Lint+Type**: `uv run ruff check . && uv run ruff format --check . && uv run mypy .` — gruen.
3. **Unit-Smoke**: `uv run pytest -q apps/api/tests/test_rate_limit.py --collect-only` — Datei importierbar, Tests collectable.
4. **Integrationstest mit DB**: `docker compose up -d && uv run pytest -q apps/api/tests/test_rate_limit.py` — alle 3 Cases gruen.
5. **Vollsuite**: `uv run pytest -q` — kein Regressionsschaden in `test_tokens.py`, `test_personas.py`, `test_playbooks.py`.
6. **Manueller Smoke gegen `uvicorn`**:
   - `uv run uvicorn who2be_api.main:app --reload`
   - 31× `curl -X POST http://localhost:8000/v1/personas -H "Authorization: Bearer <jwt>" -H "Content-Type: application/json" -d '{"slug":"t","title":"t","body":"t"}'`
   - Erwartung: ab Request 31 kommt `429 Too Many Requests`.
   - `curl http://localhost:8000/v1/personas` (GET) bleibt 200 → nicht limitiert.
7. **Web-Regression**: `npm run dev` in `apps/web/` und einmal manuell Persona anlegen → kein unbeabsichtigtes 429 unter normaler Bedienung.

## Out of Scope (bewusst)

- H2 (JSON-Logs) und H3 (security-reviewer-Pass) bleiben separate Plaene — werden nach H1-Abnahme in eigenen Plan-Dateien angegangen.
- Redis-Backend / Multi-Replica-Support — als Hinweis im Code, nicht als Implementierung.
- Rate-Limiting auf GET-Endpunkte oder MCP-Server.
- Konfigurierbare Per-Route-Limits — ein Default reicht fuer MVP.

---

## Outcome (nachgetragen)

Umgesetzt in Commit `2fdf485` auf Branch `claude/epic-archimedes-0hFfB` (PR #9).

- Implementiert wie geplant; mypy-strict erforderte einen kleinen Adapter-Wrapper
  `_on_rate_limit` in `main.py`, weil slowapis Handler auf `RateLimitExceeded`
  typisiert ist, Starlette aber `Exception` erwartet.
- `RATE_LIMIT_WRITE` zusaetzlich in `.env.example` dokumentiert.
- ADR weggelassen — nur Note in `docs/architecture.md` §6 (wie im Plan als Option vorgesehen).
- Gates lokal gruen: `ruff check`, `mypy --strict`, `pytest -q` (79 passed, 9 skipped — DB-Integrationstests inkl. der drei neuen wurden ohne Docker geskippt). Integrationstests muessen lokal gegen `docker compose up -d` nachverifiziert werden.
