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
