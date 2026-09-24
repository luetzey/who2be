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
3. `ANON_KEY` und `SERVICE_ROLE_KEY` mit dem `JWT_SECRET` erzeugen. Beide sind
   HS256-JWTs, signiert mit demselben `JWT_SECRET`, nur die `role`-Claim
   unterscheidet sie (`anon` vs. `service_role`). `--ttl` ist die Lebensdauer in
   Sekunden — `315360000` = 10 Jahre, damit die Keys nicht im laufenden Betrieb
   ablaufen (es sind langlebige Projekt-Keys, keine User-Sessions):
   ```bash
   # Aus dem Repo-Root. SECRET einmal aus der .env ziehen:
   SECRET="$(grep ^JWT_SECRET deploy/hetzner/supabase/.env | cut -d= -f2-)"

   # ANON_KEY (role=anon):
   uv run python scripts/gen_test_jwt.py --secret "$SECRET" \
       --role anon --ttl 315360000

   # SERVICE_ROLE_KEY (role=service_role):
   uv run python scripts/gen_test_jwt.py --secret "$SECRET" \
       --role service_role --ttl 315360000
   ```
   Uebernahme der beiden Ausgaben (zeichengenau, je ein langes JWT):

   | Token              | In dieser `.env` (Supabase) | Zusaetzlich in `deploy/hetzner/.env` (C3) |
   |--------------------|------------------------------|--------------------------------------------|
   | `ANON_KEY`         | `ANON_KEY=…`                 | `VITE_SUPABASE_ANON_KEY=…`                 |
   | `SERVICE_ROLE_KEY` | `SERVICE_ROLE_KEY=…`         | `SUPABASE_SERVICE_KEY=…`                   |

   > **`SERVICE_ROLE_KEY` ⇒ `SUPABASE_SERVICE_KEY`:** Das Cloud-Overlay
   > (`deploy/hetzner/who2be/docker-compose.cloud.yml`, PR #181) reicht
   > `SUPABASE_SERVICE_KEY` an die API durch — sie braucht das `service_role`-JWT
   > fuer die GoTrue-Admin-Calls (Invitation-Mail, Account-Loeschung). Fehlt der
   > Wert, werden Invitation-Mails still uebersprungen (best-effort, ADR-0023) —
   > der Token bleibt zwar gueltig, aber niemand bekommt die Mail. Der Wert in
   > beiden Files MUSS identisch sein.

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

## Mailer (Verify- + Invitation-Mails)

Die Cloud-Reise **Signup → Verify-Mail → Invitation** haengt an echter
Mail-Zustellung. GoTrue verschickt drei Mail-Typen ueber den konfigurierten
SMTP: Signup-Confirm, Password-Recovery und Invitation-Magic-Link.

**Erst-Smoke (Solo, ohne SMTP):** Fuer einen ersten Allein-Test darf
`GOTRUE_MAILER_AUTOCONFIRM=true` **voruebergehend** gesetzt werden — Signups
sind dann sofort bestaetigt, ohne Mail-Klick. Das ist ausdruecklich nur die
Ausnahme; sobald ein zweiter User per Invitation dazukommen soll, braucht es
echte Zustellung (`GOTRUE_MAILER_AUTOCONFIRM=false` + SMTP), sonst kommt die
Magic-Link-Mail nicht an.

**Produktiv (Confirm-Pflicht, `GOTRUE_MAILER_AUTOCONFIRM=false`):** SMTP-Provider
waehlen (z. B. Postmark, Mailgun, AWS SES, Brevo) und die Sender-Domain sauber
verdrahten. Checkliste fuer `GOTRUE_SMTP_ADMIN_EMAIL=no-reply@<sender-domain>`:

- [ ] **SPF**: TXT-Record der Sender-Domain listet den Provider als erlaubten
      Absender (`v=spf1 include:<provider> ~all`).
- [ ] **DKIM**: Vom Provider ausgegebene CNAME-/TXT-Records gesetzt; Signatur
      validiert (im Provider-Dashboard „verified").
- [ ] **DMARC**: `_dmarc.<sender-domain>` TXT-Record vorhanden
      (`v=DMARC1; p=quarantine; rua=mailto:…`), mindestens `p=none` zum
      Mitschneiden.
- [ ] **SMTP-Port 587** (STARTTLS) am Hetzner-Host ausgehend offen — manche
      Provider blocken 25; 587/465 sind Standard.
- [ ] **Testmail** nach dem Hochfahren: Signup mit einer Wegwerf-Adresse, in
      einem externen Postfach (nicht nur Provider-Log) den Eingang + den
      Confirm-Link pruefen.

**Mail-Link-Ziele (`GOTRUE_MAILER_URLPATHS_*`) — gegen das Web verifiziert:**
Die Pfade im Compose decken sich mit den React-Routen in
`apps/web/src/app/routes.tsx`:

| GoTrue-URLPATH        | Compose-Wert             | Web-Route (`routes.tsx`)            |
|-----------------------|--------------------------|-------------------------------------|
| `CONFIRMATION`        | `/auth/callback`         | `/auth/callback` ✓                  |
| `EMAIL_CHANGE`        | `/auth/callback`         | `/auth/callback` ✓                  |
| `RECOVERY`            | `/onboarding/set-password` | `/onboarding/set-password` ✓      |
| `INVITE`              | `/invitations`           | (Fallback — siehe Hinweis)          |

In der Praxis liefern alle App-Flows ein explizites `redirect_to` mit, das den
statischen URLPATH **ueberschreibt**: Signup/OAuth `→ /auth/callback`, Recovery
`→ /onboarding/set-password`, und die Invitation-Mail zeigt API-seitig auf
`{WEB_BASE_URL}/invitations/{token}/accept?via=magic`
(`apps/api/.../integrations/gotrue_mailer.py`). Die echte Accept-Route ist also
`/invitations/:token/accept` (Token im Pfad) — `GOTRUE_MAILER_URLPATHS_INVITE`
bleibt nur ein harmloser Default. Wichtig ist, dass `SITE_URL` dem App-Origin
(`WEB_BASE_URL`, Default `https://app.<DOMAIN>`) entspricht, damit das
`redirect_to`-Ziel die GoTrue-Allowlist (`${SITE_URL},${SITE_URL}/*`) passiert.

## Cloud-Edition: nur externe Provider (Google, GitHub)

In der **Cloud-Edition** meldet man sich ausschliesslich ueber externe Provider
an — E-Mail/Passwort ist dort abgeschaltet (Owner-Entscheidung 2026-09-24). Im
**Self-Hosting aendert sich nichts**: der Compose-Default bleibt
`GOTRUE_EXTERNAL_EMAIL_ENABLED=true`, Passwort-Login und Registrierung
funktionieren wie bisher. Es wurde nichts entfernt — das ist ein Schalter, kein
Rueckbau, und jederzeit umkehrbar.

Dafuer sind **drei** Dinge noetig, alle drei gehoeren zusammen:

**1. Eine OAuth-App bei Google und eine bei GitHub anlegen.** Die Redirect-URI
(bei Google „Authorized redirect URI", bei GitHub „Authorization callback URL")
muss **exakt** so lauten, mit `<DOMAIN>` durch die eigene Domain ersetzt — ein
Zeichen daneben und der Login scheitert mit `redirect_uri_mismatch`:

```
https://supabase.<DOMAIN>/auth/v1/callback
```

Also z. B. fuer `DOMAIN=example.com` genau `https://supabase.example.com/auth/v1/callback`.
Kein abschliessender Schraegstrich, kein `/callback` ohne `/auth/v1`, und
`https` (nicht `http`). Dieselbe URI gilt fuer **beide** Provider; sie kommt im
Compose aus `GOTRUE_EXTERNAL_{GOOGLE,GITHUB}_REDIRECT_URI` und hat genau diesen
Default — wer sie nicht ueberschreibt, muss nur den Wert oben eintragen.

Wo genau einzutragen:

| Provider | Console | Feld |
|---|---|---|
| Google | console.cloud.google.com → APIs & Services → Credentials → OAuth 2.0 Client ID (Typ „Web application") | **Authorized redirect URIs** |
| GitHub | github.com → Settings → Developer settings → OAuth Apps → New OAuth App | **Authorization callback URL** |

Bei GitHub ist zusaetzlich die „Homepage URL" Pflicht — dort `https://app.<DOMAIN>`
eintragen. Google verlangt fuer eine oeffentliche App einen konfigurierten
OAuth-Consent-Screen inklusive Links auf Datenschutz und Nutzungsbedingungen;
die liegen unter `https://app.<DOMAIN>/legal/datenschutz` bzw.
`https://app.<DOMAIN>/legal/agb`.

**2. Die Credentials in `deploy/hetzner/supabase/.env` eintragen:**

```dotenv
GOTRUE_EXTERNAL_GOOGLE_ENABLED=true
GOTRUE_EXTERNAL_GOOGLE_CLIENT_ID=<aus der Google Console>
GOTRUE_EXTERNAL_GOOGLE_SECRET=<aus der Google Console>
GOTRUE_EXTERNAL_GITHUB_ENABLED=true
GOTRUE_EXTERNAL_GITHUB_CLIENT_ID=<aus GitHub>
GOTRUE_EXTERNAL_GITHUB_SECRET=<aus GitHub>

# Erst setzen, wenn die sechs Zeilen darueber wirklich stehen:
GOTRUE_EXTERNAL_EMAIL_ENABLED=false
```

Die Reihenfolge ist kein Stil, sondern eine Sperre: `GOTRUE_EXTERNAL_EMAIL_ENABLED=false`
zuerst zu setzen, ohne dass ein Provider laeuft, sperrt **jeden** Anmeldeweg
aus — auch den eigenen.

**3. Das Web-Bundle im Cloud-Profil bauen**, damit die UI das Passwortformular
gar nicht erst zeigt: `VITE_WHO2BE_EDITION=cloud`, gesetzt vom App-Overlay
`deploy/hetzner/who2be/docker-compose.cloud.yml`. Ohne Schritt 3 blieben die
Felder sichtbar und liefen ins Leere (GoTrue antwortet dann mit 422
`email_provider_disabled`); ohne Schritt 2 waere der Login serverseitig offen,
obwohl die UI ihn versteckt. Beide zusammen, nie nur eines.

**Braucht die Cloud dann noch SMTP? Ja.** Es entfallen nur die
Bestaetigungsmail der Registrierung und die Passwort-Reset-Mail. Weiter per
Mail laufen:

| Mailpfad | Ausgeloest von | Noch aktiv? |
|---|---|---|
| **Team-Einladung** | API → `POST /auth/v1/invite` (`gotrue_mailer.py`) | **ja** — Kernfunktion |
| **E-Mail-Adresse aendern** | Konto-Einstellungen → `updateUser({ email })` | **ja** |
| Registrierungs-Bestaetigung | `POST /signup` | nein (Signup gesperrt) |
| Passwort-Reset | `POST /recover` | nein (Seite nicht erreichbar) |

Der Mailversand-Account wird also weiter gebraucht, nur mit kleinerem Volumen.
Ohne SMTP kaeme keine Einladung mehr an: die Einladung selbst bliebe zwar
gueltig (der Versand ist best-effort, der Token laesst sich manuell teilen),
aber das ist ein Notbehelf, kein Betriebsmodus.

**Team-Einladungen brechen durch den Schalter nicht.** GoTrue v2.158.1 prueft
`External.Email` nur in `POST /signup`, `POST /token?grant_type=password` und
`POST /magiclink`. `POST /invite`, `POST /verify`, `POST /recover` und
`PUT /user` haben keinen solchen Check — der Einladungsweg der App
(`POST /auth/v1/invite` mit `service_role`-Key) ist davon unberuehrt. Ein
eingeladener Nutzer, der noch kein Konto hat, landet ueber den Magic-Link
eingeloggt auf `/invitations/:token/accept`.

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
- `GOTRUE_MAILER_AUTOCONFIRM` ist im Compose default `false` (Confirm-Pflicht,
  Cloud-Paritaet). Fuer einen ersten Solo-Smoke OHNE SMTP darf der Wert in der
  `.env` voruebergehend auf `true` (siehe Abschnitt „Mailer"); produktiv bleibt
  er `false` + echter SMTP-Provider.
- Ohne gesetzten `SERVICE_ROLE_KEY` (bzw. `SUPABASE_SERVICE_KEY` in `../.env`)
  werden Invitation-Mails still uebersprungen — der Klartext-Token im 201-Body
  bleibt der einzige Weg, jemanden einzuladen.

## Verweis

- App-Stack: `../who2be/docker-compose.yml` (MS-2 C3).
- Backup/Restore: `../RUNBOOK.md` (kommt mit MS-2 C5).
- CI/CD: `.github/workflows/deploy.yml` (kommt mit MS-2 C4).
