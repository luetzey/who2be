# Supabase-Stack (Hetzner, MS-2 C2)

Selbst-gehostete Supabase-Komponenten fuer den Hetzner-Host. Liefert
Postgres, GoTrue (Auth) und einen nginx-Auth-Gateway als minimalen
Stack; Studio + postgres-meta sind unter dem Profil `studio`
aktivierbar.

## Reihenfolge

1. **MS-2 C1** muss durch sein (Server, Docker, Firewall, deploy-User).
2. **Diesen Stack ZUERST** starten — er erstellt das Docker-Netzwerk
   `supabase-net`, an dem der App-Stack (MS-2 C3) per `external: true`
   haengt.
3. **Anschliessend** den App-Stack
   `deploy/hetzner/who2be/docker-compose.yml` starten.

## Setup

1. `.env` anlegen:
   ```bash
   cp deploy/hetzner/supabase/.env.example deploy/hetzner/supabase/.env
   $EDITOR deploy/hetzner/supabase/.env
   ```
2. `JWT_SECRET` waehlen (mindestens 32 Zeichen!). **Identischer Wert**
   muss anschliessend in `deploy/hetzner/.env` (C3) eingetragen werden —
   sonst akzeptiert die Who2Be-API kein GoTrue-Token.
3. `ANON_KEY` und `SERVICE_ROLE_KEY` mit dem `JWT_SECRET` erzeugen:
   ```bash
   # Aus dem Repo-Root:
   uv run python scripts/gen_test_jwt.py \
       --secret "$(grep ^JWT_SECRET deploy/hetzner/supabase/.env | cut -d= -f2-)" \
       --role anon --exp $((10 * 365 * 24 * 3600))
   uv run python scripts/gen_test_jwt.py \
       --secret "$(grep ^JWT_SECRET deploy/hetzner/supabase/.env | cut -d= -f2-)" \
       --role service_role --exp $((10 * 365 * 24 * 3600))
   ```
   Beide Tokens in die `.env` eintragen; `ANON_KEY` zusaetzlich in
   `deploy/hetzner/.env` als `VITE_SUPABASE_ANON_KEY`.

4. Stack starten:
   ```bash
   docker compose \
     -f deploy/hetzner/supabase/docker-compose.yml \
     --env-file deploy/hetzner/supabase/.env \
     up -d --wait
   ```
5. Health-Check:
   ```bash
   docker compose -f deploy/hetzner/supabase/docker-compose.yml exec \
     auth-gateway wget -qO- http://127.0.0.1:9999/health
   # Erwartet: ok
   ```

## Studio (Profil `studio`)

```bash
docker compose \
  -f deploy/hetzner/supabase/docker-compose.yml \
  --profile studio \
  --env-file deploy/hetzner/supabase/.env up -d --wait
```

Studio laeuft auf Port 3000 im `supabase-net` — vom Server aus per
SSH-Tunnel erreichbar:
```bash
ssh -L 3000:127.0.0.1:3000 <user>@<host>
# danach lokal http://localhost:3000 + DASHBOARD_USERNAME/PASSWORD
```

Eine `studio.<DOMAIN>`-Caddy-Route ist bewusst nicht im Caddyfile —
Studio sollte nicht oeffentlich erreichbar sein.

## Bekannte Gotchas

- `JWT_SECRET` muss in **drei** Files identisch sein:
  `deploy/hetzner/supabase/.env`, `deploy/hetzner/.env` (C3) und
  (falls Studio aktiv) `deploy/hetzner/supabase/.env` `AUTH_JWT_SECRET`
  (wird aus derselben Variable gelesen — kein doppelter Eintrag noetig).
- `supabase/postgres` initialisiert das DB-Volume nur beim **ersten**
  Start. Wenn das Volume schon existiert, werden die `init/`-Scripts
  nicht erneut ausgefuehrt — Aenderungen an `init/*.sql` greifen erst
  bei `down -v`.
- `MAILER_AUTOCONFIRM=true` ist MVP-Default: Signups gehen ohne
  Email-Bestaetigung durch. Vor Public-Beta auf `false` umstellen und
  SMTP konfigurieren.

## Verweis

- App-Stack: `../who2be/docker-compose.yml` (MS-2 C3).
- Backup/Restore: `../RUNBOOK.md` (kommt mit MS-2 C5).
- CI/CD: `.github/workflows/deploy.yml` (kommt mit MS-2 C4).
