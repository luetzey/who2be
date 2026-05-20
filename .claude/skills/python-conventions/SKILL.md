---
name: python-conventions
description: Code-, Test- und API-Konventionen fuer das Python-Backend (FastAPI + FastMCP) von Who2Be.
---

- Type Hints ueberall (mypy fehlerfrei); kleine, fokussierte Funktionen.
- API: Pydantic fuer In/Out; Pagination; Versionierung im Pfad (`/v1/`).
- Geteilte Models in `packages/models/` — von `apps/api` und `apps/mcp` importiert,
  nicht duplizieren.
- MCP: FastMCP-Tools duenn halten, Logik in Services; klare Tool-Beschreibungen.
- Tests mit pytest; bei Bugfixes erst reproduzierender Test; Edge Cases explizit.
- DB (Supabase/Postgres): keine ungeparametrisierten SQL-Strings; Migrationen
  versioniert.
- Auth: Supabase Auth (Email/Password + JWT) fuer Web, eigene API-Token-Tabelle
  fuer Agenten — Owner-Grenzen serverseitig pruefen.
- DoD: pytest gruen, ruff ohne Findings, mypy fehlerfrei.
