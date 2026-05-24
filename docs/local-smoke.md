# Lokaler End-to-End-Smoke

Manueller Happy-Path-Smoke fuer Who2Be **lokal** (vor Hetzner-Deploy).
Deckt MS-1 ab: Web-UI ↔ API ↔ Postgres ↔ MCP-Server gegen die echte
lokale Stack-Konfiguration.

> **Wer haakt ab?** Du (User). Der Sandbox-Container kann kein Supabase-
> Login und keinen Browser fahren — die Abnahme passiert auf deiner
> Workstation. Plan-Pointer: `.claude/plan/2026-05-24-1535_w6-local-smoke-doc.md`.

---

## 0 — Voraussetzungen

- `uv` installiert (`uv --version` ≥ 0.4).
- `node` + `npm` installiert (Node 20+).
- `docker` + `docker compose` lauffaehig.
- Ein Supabase-Projekt (Cloud reicht fuer den lokalen Smoke) mit:
  - `Project URL` + `anon`-Key (Project Settings → API).
  - `JWT Secret` (Project Settings → API → JWT Settings).
  - Mindestens ein Test-User mit Email/Password (Authentication → Users).

## 1 — Env vorbereiten

```bash
cp .env.example .env
```

In `.env` ausfuellen:

- `DATABASE_URL` bleibt (Compose-Default).
- `JWT_SECRET` = **exakt** Supabase-Project-JWT-Secret.
- `VITE_API_BASE_URL=http://localhost:8000`
- `VITE_SUPABASE_URL=https://<projekt>.supabase.co`
- `VITE_SUPABASE_ANON_KEY=<anon-key>`

> Mismatch beim `JWT_SECRET` ⇒ API antwortet jedes Web-Login mit 401.

## 2 — Stack starten

In drei separaten Terminals (Reihenfolge wichtig):

```bash
# Terminal A — Postgres-Stub
docker compose up -d

# Terminal B — Migrations + API
uv sync
uv run who2be-migrate
uv run uvicorn who2be_api.main:app --reload

# Terminal C — Web
cd apps/web
npm ci
npm run dev
```

Smoke-Check fuer die API (eigenes Terminal):

```bash
curl -s http://localhost:8000/v1/health
# erwartet: {"status":"ok","db":"ok"}
```

## 3 — Web-Happy-Path

UI im Browser: <http://localhost:5173>.

- [ ] **Login** — Email/Password aus dem Supabase-Test-User. Nach Erfolg
      Redirect auf `/personas`.
- [ ] **Persona anlegen** — `Neue Persona` → Name, Beschreibung, System-
      Prompt, Eigenschaften (kommagetrennt) → `Anlegen`. Redirect auf
      `/personas/:id`, "Aktuelle Version: 1" sichtbar.
- [ ] **Persona editieren** — System-Prompt aendern → `Speichern (neue
      Version)`. "Aktuelle Version: 2" und `v2 —` in der Versionsliste
      sichtbar.
- [ ] **Playbook anlegen** — Header → `Playbooks` → `Neues Playbook` →
      Name, Beschreibung, Body, Type, Tags (kommagetrennt), Triggers →
      `Anlegen`. Redirect auf `/playbooks/:id`.
- [ ] **Playbook editieren** — Body aendern → Speichern → "Aktuelle
      Version: 2" + `v2` in der Versionsliste.
- [ ] **Verknuepfen** — Zurueck auf die Persona, Multi-Select unter
      "Verknuepfte Playbooks" anhaken → `Verknuepfungen speichern` →
      Status "Verknuepfungen gespeichert.".
- [ ] **Filter** — `/playbooks` → Tag oder Trigger ins Suchfeld → Liste
      filtert client-seitig.
- [ ] **Token** — Header → `Tokens` (`/settings/tokens`) → `Token
      erstellen` → Klartext-Token (`w2b_…`) **einmal** kopieren → Banner
      schliessen. Token erscheint in der Liste. Im Test einmal `Revoke`
      auf einen Dummy ausprobieren.

## 4 — MCP-Smoke gegen die lokale API

Token aus Schritt 3 verwenden. In neuem Terminal:

```bash
export WHO2BE_API_BASE_URL=http://localhost:8000
export WHO2BE_API_TOKEN=w2b_<dein-token>
uv run python -m who2be_mcp.server
```

MCP-Client (z. B. Claude Desktop mit `who2be` in `mcpServers`) aufrufen:

- [ ] `ping` → Pong.
- [ ] `get_persona("<persona-id-oder-name>")` → liefert die in Schritt 3
      angelegte Persona inklusive aktueller Version.
- [ ] `list_playbooks()` → enthaelt das Playbook aus Schritt 3 (ggf.
      mit Tag-Filter wiederholen).
- [ ] `fetch_playbook("<playbook-id>")` → liefert Body + Tags + Trigger.

## 5 — Abnahme

| Schritt              | Abgehakt am | Beleg (Screenshot / Log) |
|----------------------|-------------|--------------------------|
| 2 — API + Web up     |             |                          |
| 3 — Web-Happy-Path   |             |                          |
| 4 — MCP-Smoke        |             |                          |

> Screenshots oder Transkript-Snippets bitte unter
> `docs/smoke-evidence/2026-…/` ablegen (Ordner bei Bedarf anlegen,
> wird nicht eingecheckt) oder in Notion an die Projektseite haengen.

## Bekannte Stolpersteine

- **401 vom Web** trotz erfolgreichem Supabase-Login → `JWT_SECRET` in
  `.env` ≠ Supabase-Project-JWT-Secret. API neu starten nach Aenderung.
- **`who2be-migrate` faellt mit `connection refused`** → Postgres-
  Container noch nicht bereit; `docker compose ps` pruefen, ggf. 2 s
  warten.
- **MCP antwortet "Nicht autorisiert"** → `WHO2BE_API_TOKEN` falsch oder
  in `/settings/tokens` revoked.
- **`/v1/health` meldet `db:"down"`** → API hat den Pool nicht gebootet;
  `DATABASE_URL` und Compose-Status pruefen.
