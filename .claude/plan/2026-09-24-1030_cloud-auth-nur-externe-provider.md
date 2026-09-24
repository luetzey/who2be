# Cloud-Auth: nur externe Provider (Google, GitHub)

Kanban `t_ce4d9a7f` · Branch `who2be/t_ce4d9a7f-cloud-auth-nur-externe-provider-google-g`

Ziel: In der **Cloud-Edition** meldet man sich ausschliesslich ueber externe
Provider an. E-Mail/Passwort wird dort **ausgeblendet** — Self-Hosting bleibt
unveraendert. Kein Code-Abbau (Owner-Entscheidung 2026-09-24).

## 1. Ausgangslage — selbst gemessen (2026-09-24, Stand 69bfeda6)

| Behauptung (PM) | Messung | Ergebnis |
|---|---|---|
| `OAuthButtons.tsx`, `AuthCallbackPage.tsx`, `OAuthConsentPage.tsx` existieren | `ls apps/web/src/features/auth/{components,pages}` | bestaetigt |
| `GOTRUE_EXTERNAL_{GOOGLE,GITHUB}_*` + `GOTRUE_EXTERNAL_EMAIL_ENABLED` in der Hetzner-Supabase-Compose | `deploy/hetzner/supabase/docker-compose.yml:89,110-117` | bestaetigt |
| `signInWithOAuth` 7x | `grep -rn … apps/ \| wc -l` = **7** | bestaetigt |
| `signInWithPassword` 39x | `grep -rn … apps/ \| wc -l` = **39** | bestaetigt (davon nur **1** Produktiv-Call: `auth/SessionProvider.tsx:188`, Rest Tests/Kommentare) |

## 2. Weiche 1 — das Edition-Merkmal (Aufgabe 1)

Es gibt **genau eines**, und zwar bereits verdrahtet (ADR-0029):

- Build-Arg `VITE_WHO2BE_EDITION` (`apps/web/Dockerfile:33`)
- → `vite.config.ts:11` leitet daraus die `define`-Konstante `__CLOUD_BUILD__` ab
- → `vite-env.d.ts:5` deklariert sie, `OrgSettingsPage.tsx:56` nutzt sie heute
  schon als einziges Edition-Gate im Web-Bundle
- Cloud-Composes setzen es gesetzt: `docker-compose.cloud.yml:97`,
  `deploy/hetzner/who2be/docker-compose.cloud.yml:104`,
  `deploy/dokploy/docker-compose.cloud.yml:88`

**Entscheidung: `__CLOUD_BUILD__` wird genutzt, kein zweiter Schalter.** Kein
Block noetig — das Merkmal existiert.

Backend-Pendant ist `WHO2BE_EDITION` (`licensing/edition.py`), gesetzt in
denselben Cloud-Overlays. Beide werden im Deploy gemeinsam gesetzt — genau das
etablierte Muster von `signupDisabled`/`GOTRUE_DISABLE_SIGNUP`.

## 3. Weiche 2 — Consent-Gate bleibt erhalten

Naheliegend waere, `/signup` in der Cloud einfach auf `/login` umzuleiten. Das
ist **falsch**: die Signup-Seite traegt die Pflicht-Checkbox fuer AGB +
Datenschutz (`SignupPage.tsx:187-231`), die die OAuth-Buttons bis zur
Zustimmung `disabled` haelt (`OAuthButtons.tsx:41`). Ein Redirect wuerde den
einzigen Consent-Gate der Registrierung entfernen.

**Entscheidung:** `/signup` bleibt in der Cloud bestehen, verliert aber das
E-Mail/Passwort/Wiederholung-Formular. Consent-Checkbox + OAuth-Buttons
bleiben, der Registrieren-Link auf der Login-Seite bleibt.

## 4. Arbeitspakete

1. **Gate-Modul** `features/auth/lib/password-auth.ts` — `isPasswordAuthEnabled()`
   liest `__CLOUD_BUILD__`. Eine Stelle, testbar per `vi.mock` in beide
   Richtungen (die `define`-Konstante selbst ist ein Literal und in Vitest nicht
   stubbar).
2. **LoginPage** — Cloud: nur OAuth-Buttons (+ Registrieren-Link). Kein
   E-Mail-/Passwort-Feld, kein „Angemeldet bleiben", kein „Passwort vergessen",
   kein Resend-CTA, kein Trenner. MFA-Zweig bleibt (nur ueber Passwort-Login
   erreichbar, im Self-Hosting unveraendert).
3. **SignupPage** — Cloud: Consent + OAuth, ohne Passwortfelder.
4. **ResetPasswordPage** — Cloud: `<Navigate to="/login" replace />`
   (Direktlink-Sperre). `/onboarding/set-password` bleibt: der
   Einladungs-Magic-Link braucht sie (`InvitationAcceptPage.tsx:123`).
5. **GoTrue** — `GOTRUE_EXTERNAL_EMAIL_ENABLED` env-gesteuert, Default `true`
   (Self-Hosting unveraendert), in den Cloud-Overlays `false`.
   E2E-Overlay stellt `true` wieder her (bestehendes Muster fuer
   `GOTRUE_MAILER_AUTOCONFIRM`, `docker-compose.e2e-cloud.yml`).
6. **Doku** — `deploy/hetzner/README.md`, `deploy/hetzner/supabase/.env.example`,
   `deploy/hetzner/supabase/README.md`: OAuth-Variablen inkl. zeilengenauer
   Redirect-URI; SMTP-Antwort.
7. **Tests** — beide Richtungen (Cloud/Self-Hosting) fuer Login, Signup, Reset.
8. **Changelog** — `CHANGELOG.md` §Unreleased (es gibt **kein** `changelog.d/`
   in diesem Repo; die Karte nimmt eines an, das Repo fuehrt ein
   Keep-a-Changelog-`CHANGELOG.md`. Abweichung bewusst und gemeldet).

## 5. Befunde zu den Pflicht-Fragen

### 5.1 Team-Einladungen (Aufgabe 3) — intakt

GoTrue v2.158.1 (`image: supabase/gotrue:v2.158.1`), gegen den Quellstand
gelesen:

| Pfad | Datei/Zeile (GoTrue v2.158.1) | `External.Email.Enabled`-Check? |
|---|---|---|
| `POST /invite` (Einladung) | `internal/api/invite.go` | **nein** — kein Check im gesamten Handler |
| `POST /verify` (Link-Einloesung) | `internal/api/verify.go` | **nein** |
| `POST /recover` (Passwort-Reset-Mail) | `internal/api/recover.go` | **nein** |
| `PUT /user` (Passwort setzen) | `internal/api/user.go` | **nein** |
| `POST /signup` | `internal/api/signup.go:141` | **ja** → 400 `email_provider_disabled` |
| `POST /token?grant_type=password` | `internal/api/token.go:122` | **ja** → 422 `email_provider_disabled` |
| `POST /magiclink` | `internal/api/magic_link.go:46` | **ja** → gesperrt |

Der Einladungsweg der App ist `POST /auth/v1/invite` mit `service_role`-Key
(`apps/api/src/who2be_api/integrations/gotrue_mailer.py:51`) — **kein**
`External.Email`-Gate. Die Mail wird weiter verschickt, der Link laeuft ueber
`/verify` auf `/invitations/:token/accept?via=magic`. Einladungen brechen
**nicht**.

Genau **zwei** Wege sterben, und beide sind gewollt: Selbst-Registrierung
(`/signup`) und Passwort-Login (`/token`).

### 5.2 Braucht die Cloud noch SMTP? (Aufgabe 4) — **Ja.**

Belegstelle je Mailpfad:

| Mailpfad | Ausloeser | In der Cloud noch aktiv? |
|---|---|---|
| **Einladung** | `gotrue_mailer.py:51` → `POST /auth/v1/invite` | **JA** — Kernfunktion Team-Einladung, ohne Gate (s. o.) |
| **E-Mail-Wechsel** | `AccountPage.tsx:423` `updateUser({ email })` → GoTrue-Confirm-Mail an alte+neue Adresse | **JA** — Self-Service bleibt |
| Registrierungs-Bestaetigung | `SignupPage.tsx:91` `signUp` | nein — Signup ist in der Cloud gesperrt |
| Passwort-Reset | `ResetPasswordPage.tsx:45` `resetPasswordForEmail` | nein — Seite in der Cloud nicht erreichbar, Passwort-Login ohnehin gesperrt |
| Sonstige Benachrichtigungen | — | es gibt keine; die API hat **keinen** eigenen SMTP-Client, nur `gotrue_mailer.py` |

**Antwort fuer den Owner: Der Mailversand-Account wird gebraucht.** Er faellt
nicht weg, nur sein Volumen sinkt (keine Bestaetigungs- und Reset-Mails mehr).
Ohne SMTP kaeme keine Team-Einladung an — der Versand ist zwar best-effort
(`gotrue_mailer.py:4`, Invitation bleibt gueltig, Token manuell teilbar), aber
das ist ein Notbehelf, kein Betriebsmodell.

## 6. Verifikation

```
cd apps/web && npm run lint && npm run typecheck && npm test
```
plus die beiden CI-Bundle-Asserts (`ci.yml:197,207`), die durch den Umbau
nicht beruehrt werden.
