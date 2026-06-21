# Signup abschalten & Einladungs-Mails aktivieren

Zwei verwandte Betriebs-Aufgaben rund um die Anmeldung. Beide sind reine
**Konfiguration** (kein Code) — die App bringt die Mechanik mit.

## 1. Public-Signup abschalten

Damit sich niemand mehr selbst registriert (nur noch Einladungen), **zwei
Schalter gemeinsam** setzen:

| Variable | Ebene | Wirkung |
|---|---|---|
| `GOTRUE_DISABLE_SIGNUP=true` | Backend (GoTrue, Runtime) | **Echte Durchsetzung** — `signUp` liefert 422, auch bei direktem API-Aufruf. |
| `VITE_WHO2BE_SIGNUP_DISABLED=true` | Web-Build (Vite, Compile-Time) | Versteckt die Signup-UI: kein „Registrieren"-Link auf der Login-Seite, `/signup` leitet auf `/login` um. |

Das Backend ist die Sicherheitsgrenze; das Web-Flag entfernt nur die dann tote
UI. **Beide zusammen setzen** — sonst sieht der User entweder ein Formular, das
mit 422 scheitert (Web-Flag vergessen), oder es bleibt ein toter Link sichtbar.

- **Dokploy** (`deploy/dokploy/docker-compose.yml`): beide Variablen im
  Dokploy-Environment setzen. `VITE_WHO2BE_SIGNUP_DISABLED` ist ein **Build-Arg**
  → nach dem Setzen **neu bauen** (Redeploy mit Rebuild), nicht nur neu starten.
- **Hetzner** (`deploy/hetzner/...`): analog; Web neu bauen.

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
