# apps/api

FastAPI-Backend (REST, `/v1/`) fuer Who2Be.

Phase 0: Grundgeruest mit `/v1/health`. Persona-/Playbook-CRUD und Auth
folgen in Phase 1. Importiert geteilte Pydantic-Models aus `packages/models/`.

## Lokal starten

```bash
uv run uvicorn who2be_api.main:app --reload
```
