# Who2Be-MCP-Server in Claude Code einbinden

Ziel: Claude Code soll `mcp__who2be__*`-Tools (`ping`, `get_persona`,
`list_playbooks`, `fetch_playbook`) **nativ** aufrufen koennen — statt
sie per Python-Subprocess oder externem MCP-Client zu starten.

> **Wann brauchst du das?** Wenn du in Claude Code direkt mit deiner
> lokalen Who2Be-Persona-/Playbook-Datenbank arbeiten willst (z. B. den
> Coder-Agent gegen seine eigenen Playbooks reden lassen). Fuer den reinen
> Local-Smoke (`docs/local-smoke.md`) ist das nicht noetig.

## Zwei Wege — HTTP (Docker) oder stdio (Quellcode)

Seit der MCP-Dienst im lokalen Compose mitlaeuft, gibt es einen Weg **ohne**
Python-Toolchain. Der Rest dieses Dokuments beschreibt die stdio-Variante, die
weiterhin gilt, wenn du am Server selbst entwickelst.

| | HTTP (Compose-Dienst `mcp`) | stdio (`uv run …`) |
|---|---|---|
| Voraussetzung | nur Docker | Quellcode-Checkout + `uv` |
| Endpoint | `http://localhost:8765/mcp` (auch ueber den Web-Origin: `/mcp`) | Subprocess, kein Port |
| Auth | `Authorization: Bearer w2b_…` pro Request | `WHO2BE_API_TOKEN` als Env |
| Code-Aenderung wirkt | nach `docker compose up -d --build mcp` | sofort beim naechsten Start |

HTTP-Variante registrieren (Token vorher in der Web-UI unter
`/settings/tokens` erzeugen — dort steht die fertige Config auch zum Kopieren):

```bash
claude mcp add --transport http who2be http://localhost:8765/mcp \
  --header "Authorization: Bearer $W2B"
```

Gegenprobe ohne Client: `curl -i http://localhost:8765/mcp` muss **401** mit
`WWW-Authenticate: Bearer` liefern — das prueft auch `scripts/smoke.sh` (§6).
Kommt stattdessen HTML mit 200, sprichst du mit der Web-UI statt mit dem
MCP-Server.

## 0 — Voraussetzungen (stdio-Variante)

- Der Compose-Stack laeuft (`docker compose up -d --wait`,
  `bash scripts/smoke.sh` ist gruen) — `docs/local-smoke.md` §1+§2.
- Ein Test-User ist in GoTrue angelegt (`docs/local-smoke.md` §3, Signup-
  Snippet).
- `claude` (Claude-Code-CLI) im PATH.

## 1 — Frischen API-Token erzeugen

Der MCP-Server spricht die API als API-Token-Inhaber an, nicht als
Supabase-User. Token einmalig erzeugen — entweder per Web-UI
(`/settings/tokens` → "Token erstellen", Klartext kopieren) oder per CLI:

```bash
JWT=$(JWT_SECRET="dev-jwt-secret-change-me-32chars-min" \
      TEST_USER_ID="<deine-user-uuid>" \
      python3 scripts/gen_test_jwt.py)

W2B=$(curl -sfS -X POST http://localhost:8000/v1/tokens \
        -H "Authorization: Bearer $JWT" \
        -H "Content-Type: application/json" \
        -d '{"name":"claude-code-mcp"}' \
      | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])')
echo "$W2B"
```

Die User-UUID liest du aus dem GoTrue-Signup-Response oder per
`docker exec who2be-db-1 psql -U postgres who2be -c 'TABLE auth.users;'`.

## 2 — MCP-Server in Claude Code registrieren

```bash
claude mcp add who2be \
  -s local \
  -e WHO2BE_API_BASE_URL=http://localhost:8000 \
  -e "WHO2BE_API_TOKEN=$W2B" \
  -- /opt/homebrew/bin/uv run --project /Users/luetzey/Documents/GitHub/who2be \
       python -m who2be_mcp.server
```

- `-s local` → speichert in `~/.claude.json` unter dem aktuellen Projekt-
  Pfad. **Nicht** in `.mcp.json` (das waere project-shared und wuerde den
  Token einchecken).
- `--project ...` macht den Aufruf unabhaengig vom Claude-Code-cwd: `uv`
  findet immer den richtigen Workspace.
- Pfad zu `uv` ggf. anpassen (`which uv`).

## 3 — Health-Check

```bash
claude mcp list                       # erwarte: who2be ... ✓ Connected
claude mcp get who2be                 # Details, env-Vars, Command
```

`✓ Connected` heisst: Claude Code hat den Subprocess kurz gespawnt, einen
stdio-Handshake gefahren und die Tool-Registrierung verifiziert.

## 4 — Claude Code neu starten

MCP-Server werden beim **Session-Start** geladen. Damit die neuen
`mcp__who2be__*`-Tools in der laufenden Session auftauchen, Claude Code
einmal beenden + neu oeffnen (oder eine neue Session in diesem Projekt-
Verzeichnis starten).

Nach dem Restart koennen Aufrufe wie folgt aussehen:

- `mcp__who2be__ping()` → `"pong"`
- `mcp__who2be__list_playbooks()` → Liste deiner Playbooks
- `mcp__who2be__get_persona(identifier="<persona-id>")` → Persona + alle
  verknuepften Playbooks
- `mcp__who2be__fetch_playbook(playbook_id="<id>")` → vollstaendiger
  Playbook-Inhalt inkl. Body, Tags, Triggers

## Caveats

- **Token im Klartext** in `~/.claude.json` (user-only file-permissions).
  Wenn du das vermeiden willst: Token via Shell-env exportieren und beim
  `claude mcp add` `-e WHO2BE_API_TOKEN=$WHO2BE_API_TOKEN` (mit dem `$`
  in Quotes) verwenden — Claude Code interpoliert die env-Var dann beim
  Spawn.
- **Stack muss laufen.** Wenn der Compose-Stack down ist, antwortet jeder
  MCP-Tool-Call mit einem httpx-Connection-Error. Erkennbar in den
  Claude-Code-Logs (`claude --debug`).
- **`docker compose down -v` loescht das Postgres-Volume** und damit auch
  den API-Token. Danach: alten Server wegnehmen + frisch eintragen:
  ```bash
  claude mcp remove who2be -s local
  # Compose neu hoch, Token neu erzeugen, dann claude mcp add nochmal
  ```
- **MS-2 (Hetzner-Deploy)** wird `WHO2BE_API_BASE_URL` von
  `http://localhost:8000` auf die Hetzner-Domain umschwenken — dann
  `claude mcp remove who2be -s local` + Re-Add mit der Prod-URL.

## Verwandte Doku

- `docs/local-smoke.md` — manueller Stack-Smoke + Web-Happy-Path.
- `docs/architecture.md` + `docs/adr/0005-...` — warum MCP ein HTTP-Client
  gegen die API ist und kein DB-Direktzugriff.
