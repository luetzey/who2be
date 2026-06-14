# W6 — Web-Smoke gegen lokale API

- **Datum:** 2026-05-24
- **Notion-Task:** TASK-270 (W6 — Web-Smoke gegen lokale API)
- **Roadmap-Pointer:** `.claude/plan/2026-05-24_who2be-mvp-roadmap.md` § MS-1 / W6
- **Branch:** `claude/pensive-euler-UAAsq`

## Ziel

Ein dokumentierter, lokal nachvollziehbarer Happy-Path-Smoke fuer die
Web-UI gegen die laufende API. Output: **eine** Datei `docs/local-smoke.md`,
die als Checkliste dient — abgehakt wird sie vom User, nicht im Sandbox-
Container (kein lokales Supabase + Browser hier).

## Scope (laut Roadmap MS-1 / W6)

> Outcome: Ein `docs/local-smoke.md` beschreibt den Happy-Path (uvicorn +
> `npm run dev` + Supabase-Login + Persona/Playbook anlegen + MCP-
> `get_persona` liefert die Daten). Manuell abgehakt, Screenshots oder
> Transkript-Log beigelegt.
>
> Context: nur `docs/local-smoke.md` — laeuft parallel zu W3/W4/W5, blockt
> MS-1-Abschluss bis "abgehakt".

Disjunkt zu W1-W5: einziger Datei-Scope ist `docs/local-smoke.md`.

## Approach

Doku-Task, kein Code. Inhalt orientiert sich am tatsaechlichen Stand des
Repos:

- Lokale Infra: `docker compose up -d` (Postgres-Stub aus `docker-compose.yml`).
- Migrations: `uv run who2be-migrate` (Console-Script aus `core/migrations.py`).
- API: `uv run uvicorn who2be_api.main:app --reload` (CLAUDE.md).
- Web: `npm run dev` in `apps/web/` mit `VITE_*`-Env aus `.env.example`.
- Login: Supabase-Email/Password ueber die Web-UI (Web nutzt
  `session.access_token` als Auth-Bridge, siehe W1).
- Persona/Playbook: per Web-UI anlegen + verknuepfen (W3/W4/W5).
- Token: in `/settings/tokens` einen `w2b_`-Token erzeugen (W2).
- MCP: `WHO2BE_API_BASE_URL=http://localhost:8000` und `WHO2BE_API_TOKEN=w2b_…`
  setzen, dann `uv run python -m who2be_mcp.server` und `get_persona` durch
  einen MCP-Client (z. B. Claude Desktop) aufrufen.

## Strukturvorschlag fuer docs/local-smoke.md

1. **Voraussetzungen** — was muss installiert sein (uv, Node, Docker,
   Supabase-Projekt mit JWT-Secret).
2. **Env-Setup** — `.env` aus Vorlage, `JWT_SECRET` + `VITE_SUPABASE_*` befuellen.
3. **Stack starten** — Compose, Migrations, API, Web in dieser Reihenfolge.
4. **Web-Happy-Path** — Login → Persona anlegen → Playbook anlegen →
   verknuepfen → Versionsliste pruefen → Token erstellen.
5. **MCP-Smoke** — Env setzen, Server starten, `get_persona("…")` rufen.
6. **Abnahme-Sektion** — Checkboxen mit Platz fuer Datum + Screenshot-/
   Transkript-Pointer.

## Out of Scope

- Kein automatisierter E2E-Test (Playwright o. ae.) — bewusst manuell.
- Kein Hetzner-Smoke — der gehoert zu MS-2 / C6.
- Kein Schreiben auf Notion-DB — nur Repo-Doku.

## Verifikations-Plan

- Datei `docs/local-smoke.md` existiert, ist syntaktisch valides Markdown.
- Alle Befehle in der Datei stimmen 1:1 mit `CLAUDE.md` / `.env.example` /
  Repo-Realitaet (Console-Script-Namen, Env-Var-Praefixe).
- `npm run lint` / `tsc --noEmit` / `npm test` bleiben gruen (kein
  Code-Diff).
- `uv run pytest -q` bleibt gruen (kein Code-Diff).

## Notion-Doku-Plan

- Task TASK-270 → Review.
- Notes-Eintrag auf der Projekt-Seite mit kurzem Status + Pointer auf
  diesen Plan und `docs/local-smoke.md`.
- Hinweis im Notes-Eintrag: MS-1 ist Code-seitig fertig; das Abhaken der
  Checklist gehoert dem User.
