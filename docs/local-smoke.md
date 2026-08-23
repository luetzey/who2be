# Lokaler End-to-End-Smoke

Manueller Happy-Path-Smoke fuer Who2Be **lokal** (vor Hetzner-Deploy).
Deckt MS-1 ab: Web-UI ↔ API ↔ Postgres ↔ GoTrue (Auth) ↔ MCP-Server.

> **Wer haakt ab?** Du (User). Der Sandbox-Container kann den Browser-
> Happy-Path und das Anlegen eines Test-Users nicht selbst fahren — die
> Abnahme passiert auf deiner Workstation. Plan-Pointer:
> `.claude/plan/2026-05-25-1047_compose-smoke-pipeline.md`.

Seit der Compose-Pipeline (Mai 2026) laeuft der ganze Stack als ein
einziger `docker compose`-Aufruf — kein Supabase-Cloud-Projekt mehr
noetig fuer den lokalen Smoke.

---

## 0 — Voraussetzungen

- `docker` + `docker compose` lauffaehig (Docker Desktop oder Engine).
- Browser fuer den Web-Happy-Path.
- Optional: `curl`, `python3` auf dem Host (fuer den Smoke-Script-Lauf;
  beides ist auf macOS/Linux meist vorhanden).

`uv` und `node` werden lokal nur noch fuer die regulaeren Tests
(`uv run pytest -q`, `npm test`) gebraucht, nicht mehr fuer den Smoke.

## 1 — Stack starten

```bash
docker compose up -d --build --wait --wait-timeout 240
```

`.env` ist dafuer **nicht** noetig (jeder Wert hat einen Compose-Default);
`cp .env.example .env` nur, wenn du Defaults ueberschreiben willst. Laeuft der
Smoke gegen eine LAN-IP statt localhost, den Stack mit
`WHO2BE_PUBLIC_URL=http://<host-ip>:5173` starten und `WEB_URL`/`API_URL` beim
Skript-Aufruf entsprechend setzen.

`--wait` haelt an, bis jeder Service healthy ist (siehe `healthcheck:`-
Bloecke in `docker-compose.yml`). Reihenfolge: `db` → `migrate` (einmalig,
bringt alle SQL-Migrationen ein) → `auth` (GoTrue) + `api` → `auth-gateway`
+ `web`.

## 2 — Automatischer Smoke (curl + MCP)

```bash
bash scripts/smoke.sh
```

Pruefen wird:

1. `GET /v1/health` → `{"status":"ok","db":"ok"}`
2. `GET /` (Vite) → HTML mit `<title>`
3. JWT-authentifizierter `GET /v1/personas` (Token wird mit `scripts/gen_test_jwt.py`
   gegen `JWT_SECRET` aus `.env` erzeugt) → 200
4. MCP-Tool-Registrierung im `api`-Container → enthaelt `ping`,
   `get_persona`, `list_playbooks`, `fetch_playbook`
5. Same-Origin-Pfad ueber den Web-Origin: `/config.js` (Runtime-Config),
   `/v1/health` und `/auth/v1/health` — das ist der Weg, den der Browser geht,
   und der einzige, der auch von einer LAN-IP aus traegt
6. MCP-HTTP-Server: `401` + `WWW-Authenticate` direkt auf `:8765` und ueber den
   Web-Origin (`/mcp`), plus die Protected-Resource-Metadata. Ein `200` mit HTML
   hiesse: der SPA-Fallback greift statt des MCP-Proxys

Wenn das Skript "alle Checks gruen" druckt, ist die Basis steht. Was es
**nicht** ersetzt: das echte Web-Happy-Path-Klicken (siehe Schritt 3).

## 3 — Web-Happy-Path (manuell)

UI im Browser: <http://localhost:5173>.

Test-User vor dem allerersten Login per GoTrue-Signup anlegen:

```bash
curl -s -X POST http://localhost:9999/auth/v1/signup \
  -H "apikey: dev-anon-key-not-used-by-gotrue" \
  -H "Content-Type: application/json" \
  -d '{"email":"agent@who2be.dev","password":"streng-geheim"}'
```

(`GOTRUE_MAILER_AUTOCONFIRM=true` im Compose laesst den User sofort
einloggen — keine Bestaetigungs-Mail noetig.)

Dann im Browser:

- [ ] **Login** — Email/Password aus dem Signup-Schritt. Nach Erfolg
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

> Hinweis: Seit Phase 2.1a sind alle Inhaltspfade unter `/w/:workspaceId/...`
> (z. B. `/w/:ws/personas/:id`). Direkt-Aufrufe ohne Workspace-Prefix
> redirecten in den Default-Workspace.

## 3b — Phase-2-Flows (Status, Resources, RBAC, Dashboard)

Nach dem MVP-Happy-Path: die Phase-2-Funktionen einmal durchklicken. Reihen-
folge wichtig, weil später Schritte auf früheren Daten aufsetzen.

- [ ] **Org + Workspace** — `/settings/orgs` → `Neue Organisation` →
      `Workspace anlegen`. AppShell-Switcher zeigt beide Ebenen. Reload:
      letzte Auswahl persistiert.
- [ ] **Dashboard** — Default-Landing nach Login: `/w/:ws/dashboard`. KPIs
      (Active Personas / Playbooks / Pending Reviews) zeigen Zahlen aus dem
      MVP-Schritt. Activity-Feed bleibt leer, bis Status-Transitions laufen.
- [ ] **Draft-on-Edit** — Persona-Detail-Page → `Bearbeiten` → Speichern.
      Header: "Aktive Version: vN · Du bearbeitest: v(N+1) Draft". Zweites
      `Bearbeiten` → 409 ("Promote oder verwirf bestehenden Draft erst").
- [ ] **Status-Transitions** — auf der Draft-Version: `Zur Review einreichen`
      → Badge wird `review`. Dann `Aktivieren` (admin-only) → Badge `active`,
      die vorherige Active geht automatisch auf `inactive`. Activity-Feed im
      Dashboard zeigt zwei Einträge.
- [ ] **Resource + Block-Editor** — Header → `Resources` → `Neue Resource`.
      BlockNote-Editor öffnen, ein paar Bloecke (Heading, Paragraph,
      BulletList) einfuegen, speichern, dann promoten auf `active`.
- [ ] **Playbook-Block-Refs** — Playbook-Detail → `Bloecke verknuepfen` →
      Resource auswaehlen, einzelne Bloecke per Checkbox picken, speichern.
      Linked-Blocks-Liste zeigt Vorschau. Im Resource-Editor einen verknuepften
      Block loeschen → Playbook-Detail zeigt "Block geloescht"-Badge.
- [ ] **MCP-Read mit Active-Filter** — Token aus dem Workspace im MCP-Client
      hinterlegen. `get_persona` / `fetch_playbook` liefern nur die
      `active`-Version. `list_resources` / `fetch_resource(block_ids=…)` liefern
      die Blöcke aus dem letzten Schritt.
- [ ] **Members + Invitation** — `/w/:ws/settings/members` → `Einladen` →
      Email + Rolle `editor`. 201-Body enthaelt einmalig den Klartext-Token,
      der auch per GoTrue-Mail (falls `SUPABASE_SERVICE_KEY` gesetzt) verschickt
      wird. Token kopieren.
- [ ] **Accept-Flow** — zweite Browser-Session, anderer User: Signup, dann
      `/invitations/{token}/accept` → Redirect ins neue Workspace-Dashboard.
      Members-Tabelle zeigt beide. Doppel-Klick auf Accept → 410.
- [ ] **RBAC-Gate** — als Editor: Persona-Edit → Promote-to-Active-Button
      disabled (Tooltip "Nur Admins koennen aktivieren"). Member-Page →
      Redirect, Toast "Nur fuer Admins".

## 4 — MCP-Smoke gegen die lokale API

Token aus Schritt 3 verwenden. In neuem Terminal:

```bash
export WHO2BE_API_BASE_URL=http://localhost:8000
export WHO2BE_API_TOKEN=w2b_<dein-token>
uv run python -m who2be_mcp.server
```

> Fuer **Claude Code** geht die Anbindung sauberer ueber `claude mcp add`
> statt manuellem Start im Terminal — Setup-Anleitung in
> `docs/mcp-claude-code.md`.

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
| 1 — Stack healthy    |             |                          |
| 2 — `smoke.sh` gruen |             |                          |
| 3 — Web-Happy-Path   |             |                          |
| 4 — MCP-Smoke        |             |                          |

> Screenshots oder Transkript-Snippets bitte unter
> `docs/smoke-evidence/2026-…/` ablegen (Ordner bei Bedarf anlegen,
> wird nicht eingecheckt) oder in Notion an die Projektseite haengen.

## 6 — Teardown

```bash
docker compose down -v   # `-v` loescht das Postgres-Volume (frischer Start)
```

## Bekannte Stolpersteine

- **401 vom Web** trotz erfolgreichem Login → `JWT_SECRET` in `.env` ≠
  `GOTRUE_JWT_SECRET` im Compose. Defaults sind identisch; nach einer
  Aenderung beide synchron halten und `docker compose up -d` erneut.
- **`smoke.sh` meldet `MCP-Tool fehlt`** → der `api`-Container war nicht
  ready; `docker compose ps` und `docker compose logs api` pruefen.
- **`/v1/health` meldet `db:"unavailable"`** → API hat den Pool nicht
  gebootet; `docker compose logs db migrate` und `DATABASE_URL`
  vergleichen.
- **GoTrue-Signup gibt 422 "validation_failed"** → Passwort < 6 Zeichen
  oder schon vergebene Email.
- **MCP "Nicht autorisiert"** → `WHO2BE_API_TOKEN` falsch oder in
  `/settings/tokens` revoked.
