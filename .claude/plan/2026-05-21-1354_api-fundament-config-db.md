# Plan — API-Fundament: core/config.py + core/db.py

> Code-Task-Flow, Phase 2. Living document.
> Notion-Task: „API-Fundament: core/config.py (Settings) + core/db.py
> (asyncpg-Pool)" (PROJ-19, P0).
> Erstellt: 2026-05-21 13:54 · Branch: `claude/plan-project-VQ7T4`

## Ziel / Completion-Condition

`apps/api` hat eine zentrale Settings-Quelle und einen asyncpg-Connection-Pool
mit Lifespan-Lifecycle. Messbar erfüllt, wenn:

- `uv run ruff check .` ohne Findings
- `uv run mypy .` fehlerfrei (strict)
- `uv run pytest -q` grün (DB-Integrationstest skippt ohne erreichbare DB)
- CI-`python`-Job hat einen `postgres`-Service, sodass der Integrationstest
  dort echt läuft

## Entscheidungen

- **DB-Test-Strategie** (Anwender-Weiche): `@pytest.mark.integration`-Marker,
  Tests skippen ohne erreichbare DB; zusätzlich `postgres`-Service im CI.
- **asyncpg + mypy strict:** asyncpg liefert keine vollständigen Typen →
  bewusste, dokumentierte Ausnahme: mypy-Override `ignore_missing_imports`
  nur für `asyncpg.*` (unser Code bleibt strict).
- **Optionaler Boot:** ist die DB beim Start nicht erreichbar, loggt der
  Lifespan eine Warnung und die App startet trotzdem (Pool bleibt leer).
- **`jwt_secret` / `supabase_url` / `cors_origin`:** als Settings-Felder
  angelegt, aber noch ungenutzt (Phase 3 / Web) — Felder, keine Verdrahtung.

## Schritte

1. **Deps:** `apps/api/pyproject.toml` um `asyncpg`, `pydantic-settings`
   ergänzen; `uv sync`.
2. **`core/__init__.py`** — Paket-Marker.
3. **`core/config.py`** — `Settings(BaseSettings)` mit `database_url`
   (Default = docker-compose-Stub), `jwt_secret`, `supabase_url`,
   `cors_origin`; `get_settings()` mit `lru_cache`.
4. **`core/db.py`** — `Database`-Klasse (Pool, `connect`/`disconnect`,
   `pool`-Property, `ping()`), Modul-Singleton `database`,
   `lifespan`-Contextmanager, `get_pool()`-Dependency.
5. **`main.py`** — `lifespan` registrieren; `/v1/health` um Feld `db`
   (`"ok"` / `"unavailable"`) erweitern (`async def`).
6. **Tests:** `test_health.py` an das neue `db`-Feld anpassen; neuer
   `test_db.py` mit `@pytest.mark.integration` (skippt ohne DB).
7. **pytest-Marker** `integration` in der Root-`pyproject.toml` registrieren.
8. **mypy-Override** für `asyncpg.*` in der Root-`pyproject.toml`.
9. **CI:** `postgres:16`-Service im `python`-Job ergänzen.

## Betroffene Dateien

- `apps/api/pyproject.toml` (mod)
- `apps/api/src/who2be_api/core/__init__.py` (neu)
- `apps/api/src/who2be_api/core/config.py` (neu)
- `apps/api/src/who2be_api/core/db.py` (neu)
- `apps/api/src/who2be_api/main.py` (mod)
- `apps/api/tests/test_health.py` (mod)
- `apps/api/tests/test_db.py` (neu)
- `pyproject.toml` (mod — Marker + mypy-Override)
- `.github/workflows/ci.yml` (mod — postgres-Service)

## Verifikation

Nach Abschluss: ruff + mypy + pytest lokal; Ergebnis transkript-sichtbar
machen. Integrationstest skippt hier (keine DB), läuft in CI echt.

## Status

- [x] Schritt 1–9 abgeschlossen.
- [x] Verifiziert 2026-05-21: `ruff` clean, `mypy` strict clean (12 Dateien),
  `pytest` 3 passed / 1 skipped (DB-Integrationstest skippt ohne DB).
  asyncpg 0.31.0 installiert. CI um `postgres:16`-Service ergaenzt.
- **Abgeschlossen.**
