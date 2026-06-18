# OAuth-Connector E2E auf Dokploy (Hetzner) — Schritt für Schritt

Deployt den OAuth-fähigen Who2Be-Stack über **Dokploy** (Traefik + Let's Encrypt
statt Caddy) und verifiziert ihn mit **Claude Desktop** als LLM-Client. Du stößt
es mit einem Prompt an, Claude macht OAuth-Login + Agent-Wahl + Tool-Calls selbst.

Compose-Datei: [`deploy/dokploy/docker-compose.yml`](../deploy/dokploy/docker-compose.yml)
— ein Stack (db + auth + auth-gateway + migrate + api + web + mcp-http), **kein
Caddy**, baut die Images **aus dem Quellcode** (die ghcr-`:latest` sind veraltet
und das Web-Image ist domain-fest zur Build-Zeit).

## 0. Voraussetzungen

- Dokploy läuft auf der Hetzner-Box, Ports 80/443 frei.
- Vier **A-Records** auf die Box-IP (alle vier Pflicht):
  `api.<DOMAIN>` · `app.<DOMAIN>` · `supabase.<DOMAIN>` · `mcp.<DOMAIN>`.
- OAuth-Code ist auf `main` (PR #223 gemergt) — Dokploy baut aus `main`.

## 1. Secrets vorbereiten (lokal, einmalig)

```bash
# JWT_SECRET: >= 32 Zeichen, EINMAL erzeugen, ueberall identisch verwenden
openssl rand -base64 36

# anon-Key fuer das Web (mit GENAU diesem JWT_SECRET signieren):
uv run python scripts/gen_test_jwt.py --secret "<DEIN_JWT_SECRET>" --role anon --ttl 315360000
```
Den anon-Token merken → das ist `VITE_SUPABASE_ANON_KEY`.

## 2. Dokploy: Compose-Service anlegen

1. **Projekt anlegen** (z. B. „who2be-staging").
2. **+ Create Service → Compose**.
3. **Provider = GitHub**, Repo `luetzey/who2be`, **Branch `main`**.
4. **Compose Path:** `deploy/dokploy/docker-compose.yml`.
5. **Build Type = Docker Compose** (Dokploy baut die `build:`-Kontexte selbst).

## 3. Environment setzen

Im Service unter **Environment** (Dokploy reicht das an die Compose-Interpolation
durch):

```env
DOMAIN=<deine-domain>            # z. B. who2be.example.com → api./app./mcp. davor
POSTGRES_PASSWORD=<stark>
JWT_SECRET=<dein 32+-Zeichen-Secret aus Schritt 1>
VITE_SUPABASE_ANON_KEY=<anon-JWT aus Schritt 1>
GOTRUE_MAILER_AUTOCONFIRM=true   # Staging ohne SMTP; fuer Prod auf false + SMTP
```
Mehr ist nicht nötig — alle URLs (api./app./mcp./supabase., OAuth, VITE) leitet
die Compose aus `DOMAIN` ab.

## 4. Domains hinzufügen (Traefik-Routing)

Im Service unter **Domains** vier Einträge — jeweils Host → **Service + Port**,
HTTPS/Let's-Encrypt aktiv:

| Host                | Service        | Container-Port |
| ------------------- | -------------- | -------------- |
| `api.<DOMAIN>`      | `api`          | 8000           |
| `app.<DOMAIN>`      | `web`          | 80             |
| `supabase.<DOMAIN>` | `auth-gateway` | 9999           |
| `mcp.<DOMAIN>`      | `mcp-http`     | 8765           |

> Dokploy-Netz: Die domain-tragenden Dienste hängen in der Compose zusätzlich am
> externen `dokploy-network` (damit Traefik sie erreicht). Heißt das Netz auf
> deinem Host anders, mit `docker network ls | grep dokploy` prüfen und in
> `deploy/dokploy/docker-compose.yml` anpassen.

## 5. Deploy

**Deploy** klicken. Dokploy klont `main`, baut api/web/mcp aus dem Quellcode
(erster Build dauert ein paar Minuten), startet db → migrate → auth → api → web →
mcp-http und holt die LE-Zertifikate für die vier Hosts.

Scheitert ein Cert: DNS (Schritt 0) oder Port 80 prüfen; Dokploy-Logs des Service
zeigen den ACME-Fehler.

## 6. OAuth-Verdrahtung verifizieren

Drei curl-Checks (Details + erwartete Ausgaben in
[`docs/oauth-e2e-staging.md` §4](oauth-e2e-staging.md)):

```bash
D=<DOMAIN>
curl -fsS https://api.$D/.well-known/oauth-authorization-server | jq
curl -fsS https://mcp.$D/.well-known/oauth-protected-resource/mcp | jq   # → authorization_servers: [api.<D>]
curl -fsS -i -X POST https://mcp.$D/mcp -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}' \
  | grep -iE 'HTTP/|www-authenticate'   # → 401 + WWW-Authenticate
```

## 7. Workspace + scope-beschränkter Agent

`https://app.<DOMAIN>` → Signup → der Workspace wird mit „Builder"-Agent geseedet.
Für den Scoping-Nachweis: zweiten Agenten anlegen, Read-Scope auf **„nur
zugewiesene"** lassen, genau **ein** Playbook zuweisen
([Details: staging-Doc §5](oauth-e2e-staging.md)).

## 8. Claude Desktop verbinden + E2E anstoßen

Claude Desktop → **Einstellungen → Connectors → Custom Connector** →
`https://mcp.<DOMAIN>/mcp`. Claude öffnet den Browser-Login, zeigt die
Consent-Seite mit **Agent-Auswahl** → Agenten wählen + bestätigen.

Dann der LLM-getriebene E2E — ein Prompt, Claude verifiziert selbst
([fertiger Prompt: staging-Doc §7](oauth-e2e-staging.md)). Kurzform:

> Du bist über den Who2Be-Connector verbunden. Liste die verfügbaren Tools, ruf
> `get_persona`, `list_playbooks` und `list_triggers` auf, und prüfe: Siehst du
> nur die diesem Agenten zugewiesenen Playbooks (alle `active`)? Fasse zusammen,
> ob der Connector korrekt agent-gescopt arbeitet.

**Erwartung:** beim scope-beschränkten Agenten genau das eine zugewiesene
Playbook (nicht die Seed-Playbooks). Damit ist OAuth-Login + Agent-Bindung +
Tool-Surface + serverseitiges Read-Scoping end-to-end bewiesen — verifiziert vom
LLM.

## 9. Auto-Deploy bei jedem Push (CD)

Ziel: `git push` auf `main` → Dokploy baut + startet die neue Version
automatisch. **Funktioniert unabhängig von GitHub Actions** — Dokploy empfängt
den Push-Webhook direkt von GitHub und baut selbst (die tote CI ist irrelevant).

### Variante A — GitHub-App (empfohlen)

1. Dokploy → **Settings → Git → GitHub → Create GitHub App** (bzw. „Connect").
   Dokploy leitet zu GitHub; **App installieren** und Zugriff auf
   `luetzey/who2be` gewähren.
2. Im Compose-Service → **General/Provider**: Source von „Git URL" auf den
   verbundenen **GitHub-Provider** umstellen, Repo `luetzey/who2be`, Branch
   `main`, Compose-Path `deploy/dokploy/docker-compose.yml`.
3. Im Service den Schalter **Auto Deploy** aktivieren.

Damit registriert Dokploy automatisch den Webhook; jeder Push auf `main` löst
einen Rebuild + Restart aus.

### Variante B — Generischer Webhook (ohne GitHub-App)

1. Im Compose-Service die **Webhook-URL** kopieren (Tab „Deployments" bzw.
   „General" → „Webhook URL").
2. GitHub → Repo **Settings → Webhooks → Add webhook**:
   - **Payload URL:** die Dokploy-Webhook-URL
   - **Content type:** `application/json`
   - **Events:** „Just the push event"
   - **Active** anhaken.
3. Im Service **Auto Deploy** aktivieren.

### Testen

```bash
git commit --allow-empty -m "chore: trigger dokploy redeploy" && git push origin main
```
In Dokploy unter **Deployments** läuft sofort ein neuer Build an. Logs zeigen
`db → migrate → auth → api → web → mcp-http`.

### Hinweise

- **Branch-Filter:** Auto-Deploy feuert nur für den konfigurierten Branch
  (`main`). Feature-Branches lösen nichts aus. Tag-/Release-basiertes Deployen
  ist nicht der Standard — dafür bräuchte es einen eigenen Webhook-Filter.
- **Build-Last:** Jeder Push baut die Images neu (Docker-Layer-Cache greift, der
  Web-Build bleibt der schwerste Schritt). Auf kleinen Boxen Swap aktivieren.
- **Migrationen** laufen bei jedem Deploy (idempotent). Kurzer Restart-Downtime
  beim Compose-Redeploy ist für Staging ok.
- **Secrets bleiben in Dokploy** (Environment) — nicht im Repo. Ein Push ändert
  nur den Code, nicht die Env.

## Troubleshooting

- **`mcp.<DOMAIN>` 502** → der `mcp-http`-Dienst läuft nicht / Domain falsch
  gemappt. Dokploy-Logs prüfen.
- **Push löst keinen Deploy aus** → „Auto Deploy" aus, falscher Branch, oder der
  Webhook in GitHub liefert nicht aus (Repo → Settings → Webhooks → „Recent
  Deliveries" prüfen; muss `2xx` von Dokploy zeigen).
- **Consent endet mit Fehler** → API-Logs in Dokploy; On-Prem (Owner-DB) trifft
  der RLS-Pfad nicht.
- **Web zeigt auf localhost** → `VITE_*`-Build-Args nicht gesetzt: Web neu
  deployen, nachdem `DOMAIN` + `VITE_SUPABASE_ANON_KEY` im Environment stehen
  (Vite verdrahtet zur Build-Zeit).
- **Build schlägt fehl (out of memory)** → kleine Box: Web-Build ist der
  schwerste Schritt; ggf. Swap aktivieren oder eine größere Instanz.
