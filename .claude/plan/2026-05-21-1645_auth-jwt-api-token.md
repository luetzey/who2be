# Plan — Auth: Supabase-JWT + API-Token

> Code-Task-Flow, Phase 1 · Strang 2 von 6 (siehe `architecture.md` §8.1).
> Living document. Erstellt: 2026-05-21 16:45 · Branch: `claude/plan-project-VQ7T4`

## Ziel / Completion-Condition

Die API kann Requests beider Auth-Wege (Supabase-JWT, `w2b_`-API-Token) auf
einen `owner_id`-Kontext abbilden, und Agenten-Token sind ueber `/v1/tokens`
verwaltbar. Messbar erfuellt, wenn:

- `core/security.py` stellt `new_token`, `hash_token`, `verify_supabase_jwt`
  und die Dependency `get_current_user` bereit (ADR-0006).
- `/v1/tokens` (POST/GET/DELETE) funktioniert; der Klartext-Token erscheint
  genau einmal in der `POST`-Antwort.
- `ruff` / `mypy --strict` ohne Findings; `pytest -q` gruen.
- Unit-Tests fuer `security` (Hash, JWT-Verify, Praefix-Dispatch mit
  Fake-Repo); Integrationstests fuer `/v1/tokens` + `get_current_user`
  (skippen ohne DB, laufen im CI-`postgres`-Job).
- `security-reviewer`-Subagent hat die Auth-Implementierung geprueft
  (Repo-Vorgabe §6).

## Quelle / verbindlich

`architecture.md` §4 (`core`, repositories, services, routers), §5
(Auth-Mechanik), §6 (Sicherheit); ADR-0006. Modelle aus Strang 1
(`TokenCreate` / `TokenRead` / `TokenCreated`).

## Scope-Abgrenzung

Dieser Strang etabliert zugleich das **Schichtmuster** (ADR-0002) am
einfachsten Aggregat — API-Token, ohne Versionierung. Persona/Playbook
(Strang 3/4) kopieren das Muster und ergaenzen die Versionierung.
Persona-/Playbook-Endpunkte sind **nicht** Teil dieses Strangs.

## Komponenten

### `core/security.py`
- `new_token() -> str` — erzeugt `w2b_<secrets.token_urlsafe(32)>` (Klartext).
- `hash_token(token: str) -> str` — SHA-256-Hexdigest des gesamten Tokens.
- `verify_supabase_jwt(token: str) -> UUID` — HS256-Decode gegen
  `settings.jwt_secret`, liest `sub` als `owner_id`; wirft bei
  ungueltig/abgelaufen.
- `get_current_user(...)` — FastAPI-Dependency: liest `Authorization:
  Bearer`, entscheidet am Praefix `w2b_`:
  - `w2b_`: Token hashen, ueber das Token-Repository nachschlagen (existiert,
    nicht widerrufen) → `owner_id`; `last_used_at` best-effort aktualisieren.
  - sonst: `verify_supabase_jwt`.
  - Fehlt der Header / ungueltig / widerrufen → `HTTPException 401`.
  Liefert `owner_id: UUID`.

### `repositories/token_repository.py`
- `TokenRepository` (`Protocol`) — `insert`, `list_by_owner`,
  `fetch_owner_by_hash`, `revoke`, `touch_last_used`.
- `PgTokenRepository(pool: asyncpg.Pool)` — parametrisierte SQL-Statements,
  Row↔Model-Mapping. Keine Geschaeftsregeln.

### `services/token_service.py`
- `create(owner_id, data: TokenCreate) -> TokenCreated` — `new_token`,
  hashen, Zeile anlegen, Klartext **einmalig** zurueckgeben.
- `list(owner_id) -> list[TokenRead]`.
- `revoke(owner_id, token_id)` — setzt `revoked_at`; nur eigene Token
  (Owner-Pruefung), sonst 404.

### `routers/tokens.py`
- `POST /v1/tokens` → 201, `TokenCreated`.
- `GET /v1/tokens` → `list[TokenRead]`.
- `DELETE /v1/tokens/{id}` → 204.
- Alle Endpunkte haengen an `get_current_user` (`owner_id`).

### `main.py`
- Token-Router registrieren.

## Entscheidungen

- **JWT-Bibliothek `PyJWT`** (`pyjwt>=2.8`) — De-facto-Standard, schlank;
  neue Dependency in `apps/api/pyproject.toml`.
- **SHA-256 ohne Salt** fuer Token-Hashing — Token sind hochentropische
  Zufallswerte (kein Passwort), daher ist ein schneller Hash korrekt und
  ermoeglicht den direkten Lookup per Hash-Gleichheit (gaengige Praxis, vgl.
  GitHub-PATs). Bewusst **kein** bcrypt/argon2.
- **Praefix-Dispatch** strikt nach ADR-0006: `w2b_` → API-Token, sonst JWT.
- **`last_used_at`** wird beim erfolgreichen Token-Auth aktualisiert
  (best-effort, Fehler dort brechen den Request nicht ab).
- **Layering** wie §4: Router → Service → Repository (Protocol). Service
  haengt von der Abstraktion ab; FastAPI-`Depends` verdrahtet die konkrete
  `Pg…`-Implementierung mit dem Pool aus `get_pool`.
- `get_current_user` liefert `UUID` (reiner `owner_id`-Kontext) — kein
  Rollenmodell im MVP (ADR-0006, Konsequenzen).

## Schritte

1. `pyjwt`-Dependency in `apps/api/pyproject.toml`, `uv sync`.
2. `core/security.py` — `new_token`, `hash_token`, `verify_supabase_jwt`.
3. `repositories/` anlegen — `TokenRepository`-Protocol + `PgTokenRepository`.
4. `core/security.py` — `get_current_user` (nutzt das Token-Repository).
5. `services/token_service.py` — `create` / `list` / `revoke`.
6. `routers/tokens.py` — die drei Endpunkte; in `main.py` registrieren.
7. Unit-Tests `test_security.py`: `hash_token`-Determinismus,
   `verify_supabase_jwt` (selbst-signiertes JWT mit Test-Secret, gueltig +
   abgelaufen + falsches Secret), `get_current_user`-Dispatch mit
   In-Memory-Fake-Repo (JWT-Pfad, Token-Pfad, widerrufen, fehlender Header).
8. Integrationstest `test_tokens.py`: `/v1/tokens` POST→GET→DELETE via
   FastAPI-`TestClient` gegen echte DB; skippt ohne DB.
9. Verifikation: `ruff`, `mypy`, `pytest`.
10. `security-reviewer`-Subagent ueber die Auth-Implementierung laufen lassen;
    Findings bewerten/umsetzen.

## Betroffene Dateien

- `apps/api/pyproject.toml` (mod — `pyjwt`)
- `apps/api/src/who2be_api/core/security.py` (neu)
- `apps/api/src/who2be_api/repositories/__init__.py` (neu)
- `apps/api/src/who2be_api/repositories/token_repository.py` (neu)
- `apps/api/src/who2be_api/services/__init__.py` (neu)
- `apps/api/src/who2be_api/services/token_service.py` (neu)
- `apps/api/src/who2be_api/routers/__init__.py` (neu)
- `apps/api/src/who2be_api/routers/tokens.py` (neu)
- `apps/api/src/who2be_api/main.py` (mod — Router registrieren)
- `apps/api/tests/test_security.py` (neu)
- `apps/api/tests/test_tokens.py` (neu — Integration)

## Verifikation

`ruff` + `mypy` + `pytest` lokal. Unit-Tests (security, Service mit
Fake-Repo) laufen ohne DB; die `/v1/tokens`-Integrationstests skippen lokal
ohne DB und laufen im CI-`postgres`-Job.

## Offene Punkte

- Keine — `JWT_SECRET` ist in `config.py` bereits verankert; die
  Token-Tabelle steht aus Strang „SQL-Migrationen".

## Status

- [ ] Schritt 1–10
