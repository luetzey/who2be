# Signup abschalten & Einladungs-Mails aktivieren

Zwei verwandte Betriebs-Aufgaben rund um die Anmeldung. Beide sind reine
**Konfiguration** (kein Code) — die App bringt die Mechanik mit.

## 1. Public-Signup abschalten / "Wir arbeiten noch"-Modus

Damit sich niemand mehr selbst registriert (nur noch Einladungen), gibt es
zwei UI-Wege — **beide zusammen mit `GOTRUE_DISABLE_SIGNUP=true`**, das ist
und bleibt die eigentliche Sicherheitsgrenze (`signUp` liefert dann `422`,
auch bei direktem API-Aufruf ohne die Web-UI).

### Empfohlen: `WHO2BE_LAUNCH_MODE` (Runtime, kein Rebuild)

| Variable | Ebene | Wirkung |
|---|---|---|
| `GOTRUE_DISABLE_SIGNUP=true` | Backend (GoTrue, Runtime) | **Echte Durchsetzung** — `signUp` liefert 422, auch bei direktem API-Aufruf. |
| `WHO2BE_LAUNCH_MODE=coming_soon` | Web (Runtime, `/config.js`) | `/signup` zeigt eine Hinweisseite (DE/EN, "Wir arbeiten noch an Who2Be — bald verfügbar.") statt des Formulars; der Login-Link „Registrieren" führt dorthin statt zu verschwinden. |
| `WHO2BE_LAUNCH_CONTACT=hello@who2be.dev` (optional) | Web (Runtime) | Zeigt einen Mail-Kontakt auf der Hinweisseite. Ohne Wert entfällt der Block. |

Beide Web-Variablen wirken über `/config.js`
(`apps/web/docker/40-who2be-runtime-config.sh`, geschrieben bei jedem
Container-Start) — Umschalten braucht **keinen Rebuild**, nur Env ändern +
Container neu starten. Unbekannte `WHO2BE_LAUNCH_MODE`-Werte fallen in der
Web-UI fail-open auf `open` zurück (mit `console.warn`) — die harte Sperre
bleibt ohnehin bei GoTrue.

### Altschalter (deprecated)

| Variable | Ebene | Wirkung |
|---|---|---|
| `WHO2BE_SIGNUP_DISABLED=true` | Web (Runtime) | Versteckt Login-Link + `/signup`-Route; `/signup` leitet auf `/login` um. **Keine** Hinweisseite. |
| `VITE_WHO2BE_SIGNUP_DISABLED=true` (deprecated) | Web-Build (Vite, Compile-Time) | Gleiche Wirkung wie `WHO2BE_SIGNUP_DISABLED`, aber Build-Arg — nur relevant für Kontexte ohne `/config.js` (z. B. `npm run dev`, oder ein Bundle, das nie über den Runtime-Entrypoint läuft). |

`WHO2BE_LAUNCH_MODE=coming_soon` deckt beide Altschalter-Wirkungen ab (Signup
ist ebenfalls versteckt) und zeigt zusätzlich die Hinweisseite — neue
Deployments sollten direkt `WHO2BE_LAUNCH_MODE` nutzen. Ist nur ein Altschalter
gesetzt (kein `WHO2BE_LAUNCH_MODE`), bleibt das heutige Verhalten (toter
Redirect, kein Hinweistext) unverändert.

- **Dokploy** (`deploy/dokploy/docker-compose.yml`): `GOTRUE_DISABLE_SIGNUP`
  im Dokploy-Environment setzen. Das ältere `VITE_WHO2BE_SIGNUP_DISABLED` ist
  ein **Build-Arg** → nach dem Setzen **neu bauen** (Redeploy mit Rebuild),
  nicht nur neu starten.
- **Hetzner** (`deploy/hetzner/...`): siehe
  [RUNBOOK → Launch-Modus: Public-Signup abschalten](../deploy/hetzner/RUNBOOK.md#launch-modus-public-signup-abschalten).

Einladungen funktionieren unabhängig davon weiter (Members-Seite → Invite).

## 2. Echte Einladungs-Mails (SMTP)

Der Invite-Flow ist verkabelt: Members-Seite →
`POST /v1/workspaces/{ws}/invitations` legt eine `workspace_invitation`
(single-use, nur der sha256-Hash des Tokens wird gespeichert, gültig sieben
Tage) an und ruft danach **best-effort** GoTrue `POST /auth/v1/invite`
(`apps/api/src/who2be_api/routers/invitations.py#create_invitation`,
`apps/api/src/who2be_api/services/invitation_service.py#InvitationService`).
Der 201-Body trägt den Klartext-Token genau einmal
(`packages/models/src/who2be_models/invitation.py#InvitationCreated`).

Es gibt zwei Wege zur Annahme. Beide verlangen ein eingeloggtes Konto, dessen
E-Mail-Adresse zur Einladung passt.

### Weg A: Einladungsmail → Seite `/invitations`

Die Mail enthält **keinen Einladungs-Token**. Die API übergibt GoTrue als
`redirect_to` nur `{WEB_BASE_URL}/invitations` und schickt in `data` keine
Metadaten mit
(`apps/api/src/who2be_api/integrations/gotrue_mailer.py#send_invitation_email`,
`apps/api/src/who2be_api/integrations/gotrue_mailer.py#build_invitations_url`).
So steht der Token weder in einer Query, die Proxies mitloggen, noch in den
Benutzer-Metadaten, die in jedem Access-Token landen.

1. Der Link in der Mail zeigt auf GoTrue (`/auth/v1/verify` hinter dem
   Auth-Gateway, nicht auf die Web-App). GoTrue prüft dort seinen eigenen
   Einmal-Token, meldet den Eingeladenen an und leitet auf `redirect_to` um;
   die Session reist im URL-Fragment mit. Welcher `GOTRUE_MAILER_URLPATHS_*`-
   Wert dafür im Compose stehen muss und warum, steht in
   [`deploy/hetzner/supabase/README.md` → Mailer](../deploy/hetzner/supabase/README.md#mailer-verify---invitation-mails)
   — hier bewusst nicht wiederholt.
2. `{WEB_BASE_URL}/invitations` ist eine geschützte Route
   (`apps/web/src/app/routes.tsx#RouterRoot`, unter `RequireAuth`). Ohne
   Session geht es zum Login und per `next=/invitations` zurück.
3. Ein Konto, das GoTrue gerade erst per Invite angelegt hat, hat noch kein
   Passwort. Die Seite schickt es zuerst auf `/onboarding/set-password` und
   danach zurück
   (`apps/web/src/features/auth/pages/PendingInvitationsPage.tsx#PendingInvitationsPage`).
4. Die Seite listet die offenen Einladungen an die Adresse des Kontos, über
   alle Workspaces hinweg: `GET /v1/invitations/pending`
   (`apps/api/src/who2be_api/routers/invitations.py#list_pending_invitations`).
   Die Antwort trägt weder Token noch Token-Hash
   (`apps/api/src/who2be_api/routers/invitations.py#PendingInvitationRead`).
5. Angenommen wird per Klick über die ID:
   `POST /v1/invitations/pending/{invitation_id}/accept`
   (`apps/api/src/who2be_api/routers/invitations.py#accept_pending_invitation`).
   Danach geht es ins Dashboard des Workspace.

Beide Pending-Endpunkte antworten nur, wenn GoTrue die Adresse des Kontos als
**bestätigt** führt
(`apps/api/src/who2be_api/services/invitation_service.py#PendingInvitationService`):
ohne `email`-Claim `403 invitation_email_required`, ohne Bestätigung
`403 invitation_email_unconfirmed`. Fremde oder unbekannte ID: `404`;
angenommen, widerrufen oder abgelaufen: `410`. Warum das an
`GOTRUE_MAILER_AUTOCONFIRM` hängt, steht in der Warnung im
[Supabase-README](../deploy/hetzner/supabase/README.md#mailer-verify---invitation-mails).

**Neue bzw. registrierte Adresse.** Gibt es zur Adresse noch kein Konto, legt
GoTrue beim Invite eines ohne Passwort an und verschickt die Mail (Schritte
1–5 inklusive Passwort setzen). Gibt es ein Konto, dessen Adresse **noch nicht
bestätigt** ist, verschickt GoTrue die Mail erneut. Ist die Adresse eines
bestehenden Kontos **bereits bestätigt**, lehnt GoTrue den Invite ab (`422`,
`email_exists`; GoTrue v2.197.0, `internal/api/invite.go`, `Invite`) — es
geht **keine Mail** raus, die API loggt den Fehlschlag nur als Warnung. Die
Einladung ist trotzdem gültig und steht auf `/invitations`, sobald die Person
eingeloggt dort ist. Einen Hinweis darauf in der App gibt es bisher nicht;
für registrierte Nutzer ist deshalb Weg B der verlässliche.

### Weg B: geteilter Link mit Token im Fragment

Die Members-Seite bietet zu einer offenen Einladung „Link kopieren" an —
nur solange sie den Token kennt, also direkt nach dem Einladen (danach ist der
Knopf deaktiviert, gespeichert ist nur der Hash). Der Link hat die Form
`{Web-Origin}/invitations/accept#token=…`
(`apps/web/src/features/settings/pages/MembersPage.tsx#acceptUrl`). Der Token
steht **nur im URL-Fragment**, nicht im Pfad und nicht in der Query: das
Fragment verlässt den Browser nicht und landet deshalb in keinem Server- oder
Proxy-Log.

Die Seite `/invitations/accept` ist öffentlich
(`apps/web/src/app/routes.tsx#RouterRoot`). Sie liest den Token aus dem
Fragment, legt ihn für die Dauer des Tabs im `sessionStorage` ab und räumt die
Adresszeile; so übersteht er Login und Passwort-Setzen, ohne je in einer URL
zu stehen
(`apps/web/src/features/auth/pages/InvitationAcceptPage.tsx#InvitationAcceptPage`).
Nach dem Klick auf „Einladung annehmen" geht der Token im Body an
`POST /v1/invitations/accept`
(`apps/web/src/api/client.ts#acceptInvitation`,
`apps/api/src/who2be_api/routers/invitations.py#accept_invitation_by_body`).
Die Login-Adresse muss zur Einladung passen, sonst `403`
(`invitation_email_required` bzw. `invitation_email_mismatch`).

### Abgelöst: Token im Pfad

Bis S2b trug der Mail-Link den Token im Pfad
(`/invitations/{token}/accept?via=magic`, Auto-Accept nach dem Login). Dieser
Altablauf ist abgelöst. Übergangsweise bleiben erreichbar, damit bereits
verschickte Links nicht brechen:

- die Web-Route `/invitations/:token/accept` — sie nimmt ebenfalls per Body an
  und räumt die Adresse (`apps/web/src/app/routes.tsx#RouterRoot`);
- der API-Pfad `POST /v1/invitations/{token}/accept`, als `deprecated`
  markiert, mit `Sunset`-Header
  (`apps/api/src/who2be_api/routers/invitations.py#accept_invitation`,
  Datum in `apps/api/src/who2be_api/routers/invitations.py#_LEGACY_SUNSET`).

Neue Links erzeugt nichts mehr in dieser Form.

### Voraussetzungen für den Mailversand

Damit GoTrue die Mail wirklich **versendet**, brauchst du:

1. **SMTP in GoTrue** (Compose-`auth`-Service ist vorbereitet):
   `GOTRUE_SMTP_HOST`, `GOTRUE_SMTP_PORT`, `GOTRUE_SMTP_USER`,
   `GOTRUE_SMTP_PASS`, `GOTRUE_SMTP_ADMIN_EMAIL`, `GOTRUE_SMTP_SENDER_NAME`.
2. **`GOTRUE_MAILER_AUTOCONFIRM=false`** (sonst werden Bestätigungs-Mails
   übersprungen).
3. **API → GoTrue-Admin**: `SUPABASE_SERVICE_KEY` (service_role-JWT) +
   `SUPABASE_URL` müssen für `apps/api` gesetzt sein, sonst überspringt der
   Mailer den Versand (Log: „GoTrue nicht konfiguriert"). `WEB_BASE_URL` muss
   auf den öffentlichen App-Origin zeigen (Ziel `redirect_to` der Mail).
4. **GoTrue-Seite**: Mail-Link-Pfad und Redirect-Allowlist (`SITE_URL`) wie in
   [`deploy/hetzner/supabase/README.md` → Mailer](../deploy/hetzner/supabase/README.md#mailer-verify---invitation-mails)
   beschrieben.

**Fallback ohne SMTP:** Die Invitation ist trotzdem gültig — der 201-Body
enthält den Klartext-Token, die Members-Seite macht daraus direkt nach dem
Einladen den Fragment-Link aus Weg B (`/invitations/accept#token=…`), den der
Admin manuell teilt.

> Lokal nimmt **Mailpit** (UI `http://localhost:8025`) jede Mail an — die
> `GOTRUE_SMTP_*`-Defaults in `.env.example` reichen für den Smoke.

### Self-Hosting ohne Mailversand

Die Cloud-Version braucht Mailversand. Die On-Prem-Edition soll bewusst auch
**ohne** Mailversand laufen. Deshalb steht im Dokploy-Compose
(`deploy/dokploy/docker-compose.yml`, Dienst `auth`) der Default
`GOTRUE_MAILER_AUTOCONFIRM=true`; der Hetzner-Compose setzt `false`.

> **Hinweis: Autoconfirm ist nur für lokalen Betrieb oder ein
> vertrauenswürdiges Netz gedacht.** Mit `GOTRUE_MAILER_AUTOCONFIRM=true` gilt
> jede bei der Registrierung angegebene Adresse sofort als bestätigt — ohne
> dass jemand das Postfach geöffnet hat. Die Bestätigung ist dann **kein
> Besitznachweis**. Die offenen Einladungen (Weg A, `/v1/invitations/pending`)
> hängen aber genau an dieser bestätigten Adresse.
>
> Ist die Instanz öffentlich erreichbar, gehört
> `GOTRUE_MAILER_AUTOCONFIRM=false` gesetzt und echter SMTP verdrahtet
> (`GOTRUE_SMTP_*`, siehe „Voraussetzungen für den Mailversand"). Stand heute
> reicht der Dokploy-Compose `GOTRUE_SMTP_*` **nicht** an den `auth`-Dienst
> durch — Variablen nur in der Dokploy-Environment zu setzen, genügt dort
> also nicht. Ohne SMTP bleibt Weg B (geteilter Link) der Einladungsweg.
>
> Hintergrund und dieselbe Warnung für den Hetzner-Betrieb:
> [Supabase-README → Mailer](../deploy/hetzner/supabase/README.md#mailer-verify---invitation-mails).

## 3. Captcha vor der Registrierung (Cloudflare Turnstile)

Gegen Massen-Signups steht optional ein Captcha vor der Selbstregistrierung.
Anbieter ist **Cloudflare Turnstile** (kein Bilderrätsel, datensparsam, AVV
verfügbar). Der Schalter ist **standardmäßig aus** — ohne gesetzte Schlüssel
verhält sich die Registrierung exakt wie vorher, es wird kein Widget
gerendert und kein Request an Cloudflare gesendet.

### Schlüssel anlegen

Cloudflare-Dashboard → **Turnstile** → *Add Site*, Widget-Modus „Managed",
Domain = die App-Domain. Du erhältst ein Paar:

| Schlüssel | Gehört wohin | Sichtbarkeit |
|---|---|---|
| **Site Key** | Web-App (`WHO2BE_TURNSTILE_SITE_KEY`) | öffentlich — steht im ausgelieferten HTML |
| **Secret Key** | GoTrue (`GOTRUE_SECURITY_CAPTCHA_SECRET`) | geheim — verlässt den Server nie |

### Einschalten

Beide Hälften gehören zusammen. Nur eine zu setzen **bricht die
Registrierung**: mit Secret ohne Site-Key schickt die Web-App kein Token und
GoTrue lehnt ab; mit Site-Key ohne Secret zeigt die App ein Widget, dessen
Token niemand prüft.

| Variable | Ebene | Wirkung |
|---|---|---|
| `GOTRUE_SECURITY_CAPTCHA_ENABLED=true` | Backend (GoTrue, Runtime) | **Echte Durchsetzung** — ohne gültiges Token `400 captcha_failed`, auch bei direktem API-Aufruf. |
| `GOTRUE_SECURITY_CAPTCHA_PROVIDER=turnstile` | Backend | Anbieter. Erlaubt sind `turnstile` und `hcaptcha`; der Compose-Default ist `turnstile`. |
| `GOTRUE_SECURITY_CAPTCHA_SECRET=…` | Backend | Secret Key. Bei `ENABLED=true` **Pflicht** — fehlt er, startet GoTrue nicht. |
| `WHO2BE_TURNSTILE_SITE_KEY=…` | Web (Runtime, `/config.js`) | Rendert das Widget auf Registrierung, Login und „Passwort vergessen" und schickt das Token mit. Leer = kein Widget. |

Die Namen sind gegen die im Compose gepinnte GoTrue-Version **v2.158.1**
verifiziert (`internal/conf/configuration.go`, `CaptchaConfiguration` +
`SecurityConfiguration`, envconfig-Präfix `gotrue`). Achtung, hier lauert ein
naheliegender Fehler: das Secret heißt per Env **`..._CAPTCHA_SECRET`**, nicht
`..._CAPTCHA_PROVIDER_SECRET` — `envconfig` bildet den Go-Feldnamen `Secret`
ab, nicht das JSON-Tag `provider_secret`.

Die Web-Variable wirkt über `/config.js`
(`apps/web/docker/40-who2be-runtime-config.sh`) — Umschalten braucht **keinen
Rebuild**, nur Env ändern + Container neu starten.

### Was das Captcha sonst noch trifft

GoTrue hängt die Prüfung nicht nur an `/signup`, sondern an **alle**
unauthentifizierten Auth-Endpunkte: `/recover` (Passwort vergessen),
`/resend` (Bestätigungs-Mail erneut senden), `/magiclink`, `/otp`, `/sso` und
den Passwort-Login (`/token` mit `grant_type=password`).

Die Web-App liefert an **allen Pfaden, die sie selbst anbietet**, ein Token:
Registrierung, Passwort-Login, „Bestätigungs-Mail erneut senden" und
„Passwort vergessen". Login und Resend teilen sich dabei das eine Widget der
Login-Maske — ein Turnstile-Token ist einmalig gültig, die Challenge wird
deshalb nach jedem Request neu gestellt. `/magiclink`, `/otp` und `/sso` ruft
die App nicht auf.

**Nicht betroffen** (und das ist der wichtige Teil für das
Einladungs-Onboarding):

- **Invite-Versand** — läuft als Admin-Call mit dem Service-Role-Key; GoTrue
  überspringt die Captcha-Prüfung für Admin-Credentials.
- **Magic-Link-Einlösung** (`/verify`) — trägt die Captcha-Middleware gar
  nicht erst.

Eingeladene Nutzer kommen also unverändert durch, auch mit aktivem Captcha.

### Datenschutz

Turnstile ist ein **Drittland-Empfänger** (Cloudflare, USA). Solange kein
Site-Key gesetzt ist, wird das Script nicht geladen und es entsteht kein
Transfer. Wer einschaltet, trägt Cloudflare in die Datenschutzerklärung und
das Verarbeitungsverzeichnis ein — Checkliste:
[`compliance/legal-texts-checklist.md` §2](compliance/legal-texts-checklist.md).

