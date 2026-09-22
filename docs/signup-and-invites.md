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

Der Invite-Flow ist verkabelt: Members-Seite → `POST .../invitations` legt eine
`workspace_invitation` (single-use, sha256-Token) an und ruft **best-effort**
GoTrue `POST /auth/v1/invite`. Der Magic-Link landet auf
`{WEB_BASE_URL}/invitations/{token}/accept?via=magic` (Auto-Accept nach Login).

Damit GoTrue die Mail wirklich **versendet**, brauchst du:

1. **SMTP in GoTrue** (Compose-`auth`-Service ist vorbereitet):
   `GOTRUE_SMTP_HOST`, `GOTRUE_SMTP_PORT`, `GOTRUE_SMTP_USER`,
   `GOTRUE_SMTP_PASS`, `GOTRUE_SMTP_ADMIN_EMAIL`, `GOTRUE_SMTP_SENDER_NAME`.
2. **`GOTRUE_MAILER_AUTOCONFIRM=false`** (sonst werden Bestätigungs-Mails
   übersprungen).
3. **API → GoTrue-Admin**: `SUPABASE_SERVICE_KEY` (service_role-JWT) +
   `SUPABASE_URL` müssen für `apps/api` gesetzt sein, sonst überspringt der
   Mailer den Versand (Log: „GoTrue nicht konfiguriert"). `WEB_BASE_URL` muss
   auf den öffentlichen App-Origin zeigen (für den Accept-Link).

**Fallback ohne SMTP:** Die Invitation ist trotzdem gültig — der 201-Body
enthält den Klartext-Token; den Accept-Link
(`{WEB_BASE_URL}/invitations/{token}/accept?via=magic`) kann der Admin manuell
teilen.

> Lokal nimmt **Mailpit** (UI `http://localhost:8025`) jede Mail an — die
> `GOTRUE_SMTP_*`-Defaults in `.env.example` reichen für den Smoke.

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

