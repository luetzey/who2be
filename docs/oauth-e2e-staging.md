# OAuth-Remote-MCP-Connector — echter E2E auf Staging (mit Claude Desktop als LLM)

Ziel: den OAuth-Connector **live** über echtes HTTPS testen und die Verifikation
von **Claude Desktop selbst** fahren lassen — du stößt es mit einem Prompt an,
das LLM macht Login + Agent-Wahl + Tool-Calls und berichtet, ob alles stimmt.

Das ist der echte LLM-getriebene E2E: kein API-Key, kein Skript. Claude Desktop
ist der MCP-Client. Voraussetzung ist nur ein öffentlich erreichbarer Stack
(api./app./mcp.<DOMAIN> über HTTPS).

> Edition: Diese Anleitung nutzt die **On-Prem-Edition** (Default-Compose) — der
> einfachste Weg zu einem öffentlichen Stack. Der Cloud-RLS-Pfad (`who2be_app`)
> ist lokal bereits bewiesen (`scripts/oauth_smoke.sh cloud`). Wer Cloud live
> will, legt das `docker-compose.cloud.yml`-Overlay drauf (siehe RUNBOOK).

---

## 1. Voraussetzungen

- Eine Box mit öffentlicher IP (Hetzner o. ä.), Docker + Compose v2, Ports
  80/443 offen. Provisioning-Details: `deploy/hetzner/RUNBOOK.md` §Provisioning.
- Eine Domain, bei der du **vier A-Records** auf die Box-IP setzen kannst.
  `mcp.<DOMAIN>` ist hier — anders als im RUNBOOK (dort „optional") — **Pflicht**:

  | Record              | Pflicht | Backend            |
  | ------------------- | ------- | ------------------ |
  | `api.<DOMAIN>`      | ja      | api:8000 (OAuth-AS)|
  | `app.<DOMAIN>`      | ja      | web:80 (Consent)   |
  | `supabase.<DOMAIN>` | ja      | auth-gateway:9999  |
  | `mcp.<DOMAIN>`      | **ja**  | mcp-http:8765 (RS) |

  DNS **vor** dem Caddy-Start auflösen lassen (sonst scheitert die ACME-Challenge):
  ```bash
  for s in api app supabase mcp; do dig +short ${s}.<DOMAIN>; done   # je Box-IP
  ```

---

## 2. Repo + `.env` auf die Box

```bash
git clone https://github.com/luetzey/who2be.git /opt/who2be && cd /opt/who2be

cp deploy/hetzner/.env.example deploy/hetzner/.env
$EDITOR deploy/hetzner/.env          # DOMAIN, ACME_EMAIL, JWT_SECRET, SUPABASE_URL,
                                     # CORS_ORIGINS=https://app.<DOMAIN>, VITE_*
chmod 600 deploy/hetzner/.env

cp deploy/hetzner/supabase/.env.example deploy/hetzner/supabase/.env
$EDITOR deploy/hetzner/supabase/.env # POSTGRES_PASSWORD, JWT_SECRET (IDENTISCH zu oben!)
chmod 600 deploy/hetzner/supabase/.env
```

Für einen ersten Solo-Smoke darf `GOTRUE_MAILER_AUTOCONFIRM=true` bleiben (kein
SMTP nötig — Signups sind sofort nutzbar). Die OAuth-URLs musst du **nicht**
setzen: sie leiten sich im Compose automatisch aus `DOMAIN` ab (ADR-0036).

---

## 3. Stack hochfahren — **mit `--profile mcp-http`**

```bash
# 1) Supabase-Stack (Postgres + GoTrue)
docker compose \
  -f deploy/hetzner/supabase/docker-compose.yml \
  --env-file deploy/hetzner/supabase/.env \
  up -d --wait

# 2) App-Stack INKL. MCP-HTTP — das --profile ist hier der entscheidende Zusatz
docker compose \
  -f deploy/hetzner/who2be/docker-compose.yml \
  --env-file deploy/hetzner/.env \
  --profile mcp-http \
  up -d --wait
```

Caddy holt sich beim ersten Start automatisch Let's-Encrypt-Zertifikate für alle
vier Subdomains (inkl. `mcp.`). Scheitert die Cert-Ausstellung, sind es fast
immer DNS (Schritt 1) oder Port 80 (Firewall).

---

## 4. OAuth-Verdrahtung verifizieren (vor dem Client)

```bash
D=<DOMAIN>

# AS gesund + Metadaten (RFC 8414) — muss authorization/token/registration zeigen
curl -fsS https://api.$D/v1/health
curl -fsS https://api.$D/.well-known/oauth-authorization-server | jq

# Protected-Resource-Metadata des MCP-Servers (RFC 9728) — zeigt auf den AS
curl -fsS https://mcp.$D/.well-known/oauth-protected-resource/mcp | jq
#   → "authorization_servers": ["https://api.<DOMAIN>"]

# MCP ohne Token → 401 + WWW-Authenticate (das ist der OAuth-Trigger)
curl -fsS -i -X POST https://mcp.$D/mcp \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}' \
  | grep -iE 'HTTP/|www-authenticate'
#   → 401 + WWW-Authenticate: Bearer ... resource_metadata="https://mcp.<DOMAIN>/..."
```

Sehen alle drei gut aus, ist der Connector bereit.

---

## 5. Workspace + Agent anlegen (damit es etwas zu prüfen gibt)

1. `https://app.<DOMAIN>` öffnen → Signup (Autoconfirm: sofort eingeloggt).
2. Ein Workspace wird automatisch geseedet: Persona „Builder" + 4 Builder-
   Playbooks + ein **Builder-Agent** (liest alles — gut für den ersten Smoke).
3. **Für den Scoping-Nachweis** (empfohlen): einen zweiten Agenten anlegen, ihm
   in der Agent-Konfiguration den Read-Scope **„nur zugewiesene"** lassen
   (secure-by-default) und genau **ein** Playbook zuweisen. So lässt sich später
   prüfen, dass der Connector wirklich nur das Zugewiesene sieht.

---

## 6. Connector in Claude Desktop hinzufügen

In Claude Desktop (oder claude.ai): **Einstellungen → Connectors → Custom
Connector hinzufügen** → URL `https://mcp.<DOMAIN>/mcp`.

Claude entdeckt darüber automatisch den Authorization-Server, öffnet den
**Browser-Login** bei Who2Be, zeigt die **Consent-Seite mit Agent-Auswahl**
(`https://app.<DOMAIN>/oauth/consent`) — wähle den gewünschten Agenten und
bestätige. Danach ist der Connector verbunden; kein Token-Copy-Paste.

---

## 7. Den E2E anstoßen — Claude Desktop macht den Rest

Jetzt der eigentliche LLM-getriebene Test: ein Prompt, das LLM fährt die
Verifikation. Beispiel (mit dem **scope-beschränkten** Agenten verbunden):

> Du bist über den Who2Be-Connector verbunden. Bitte verifiziere systematisch:
> 1. Liste die verfügbaren MCP-Tools auf.
> 2. Rufe `get_persona` auf und nenne Name + ob eine aktive Version existiert.
> 3. Rufe `list_playbooks` auf und liste alle sichtbaren Playbooks mit Status.
> 4. Rufe `list_triggers` auf.
> 5. Bewerte: Siehst du **nur** die diesem Agenten zugewiesenen Playbooks oder
>    mehr? Sind alle sichtbaren Versionen `active`?
> 6. Fasse zusammen, ob der Connector korrekt agent-gescopt arbeitet.

**Erwartung (korrekt):**
- Tools erscheinen (`get_persona`, `list_playbooks`, `fetch_playbook`,
  `list_resources`, `fetch_resource`, `fetch_agent`, `list_triggers`).
- `list_playbooks` zeigt beim scope-beschränkten Agenten **genau das eine
  zugewiesene** Playbook (nicht die 4 Seed-Playbooks), alle `active`.
- Beim Builder-Agenten dagegen alle aktiven Playbooks (read=all).

Damit hast du bewiesen: OAuth-Login, Agent-Bindung, Tool-Surface und das
serverseitige Read-Scoping greifen end-to-end — verifiziert vom LLM selbst.

Optional negativ: Token im Web-UI revoken (`/settings` → Tokens) → der Connector
liefert beim nächsten Tool-Call 401, Claude meldet „nicht mehr autorisiert".

---

## Troubleshooting

- **Cert/ACME scheitert** → DNS (Schritt 1) oder Port 80 zu. `docker compose …
  logs caddy` zeigt den ACME-Fehler im Klartext.
- **Claude verbindet, aber keine Tools** → PRM/AS-Metadaten (Schritt 4) prüfen;
  `MCP_RESOURCE_URL` (api) muss exakt `https://mcp.<DOMAIN>/mcp` sein
  (`docker compose … exec api printenv MCP_RESOURCE_URL`).
- **Consent endet mit Fehler** → in der API-Log nach `who2be_app`/RLS schauen;
  On-Prem (Owner-DB) sollte das nicht treffen. `docker compose … logs api`.
- **`mcp.<DOMAIN>` 502** → `--profile mcp-http` vergessen; der MCP-Container läuft
  dann nicht.
