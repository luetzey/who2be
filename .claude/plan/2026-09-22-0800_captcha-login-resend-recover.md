# Captcha aktiv ⇒ Passwort-Login, Resend und Recover mit Token versorgen

Karte: t_c007ed1d (Folgebefund aus dem Review von #539 / PR #558)
Branch: `p_2d6a9710/t_c007ed1d-captcha-aktiv-passwort-login-und-mail-er`
Basis: `origin/wt/i539-turnstile` (ac3bdb2) — die Karte baut auf dem noch
offenen PR #558 auf, nicht auf `main`; `TurnstileWidget` existiert erst dort.

## Ausgangslage (am Quelltext geprüft)

- GoTrue v2.158.1 hängt `verifyCaptcha` an `/signup`, `/recover`, `/resend`,
  `/magiclink`, `/otp`, `/token` und `/sso`; `isIgnoreCaptchaRoute` nimmt nur
  `/token` mit `grant_type != password` aus.
- Die Web-App schickt heute nur in `SignupPage.tsx` ein `captchaToken`.
- Betroffene App-Pfade, die es wirklich gibt:
  - Passwort-Login → `SessionProvider.signIn` → `signInWithPassword` (`/token`)
  - „Bestätigungs-Mail erneut senden" → `LoginPage.resendConfirmation` → `resend` (`/resend`)
  - Passwort vergessen → `ResetPasswordPage` → `resetPasswordForEmail` (`/recover`) — Punkt 3 der Karte: **ja, die App bietet den Pfad an** (`/reset-password`, verlinkt aus der Login-Maske).
  - Magic-Link/OTP/SSO: die App ruft sie nicht auf → nicht betroffen.
- `@supabase/supabase-js` 2.112.3 trägt `captchaToken` an allen drei Aufrufen
  (`auth-js/GoTrueClient.d.ts:2138-2141` für `resetPasswordForEmail`,
  `lib/types.d.ts` für `SignInWithPasswordCredentials.options` und `ResendParams.options`).

## Entscheidungen

1. **Gemeinsame Stelle statt Kopie.** `isCaptchaError` + `translateSignupError`
   wandern aus `SignupPage.tsx` nach `features/auth/lib/captcha.ts`
   (`translateAuthError`, pure, direkt testbar). Dazu ein Hook
   `features/auth/lib/use-captcha.ts`, der den dreifach identischen
   React-Zustand (Token, Remount-Nonce, `required`) hält — sonst stünde
   derselbe Fünfzeiler in drei Seiten.
2. **`action` je Pfad.** `TurnstileWidget` bekommt ein `action`-Prop
   (`signup` | `login` | `resend` | `recover`). Cloudflare wertet die Action
   in der Analytics/Rate-Rule aus; ohne sie sähen alle vier Pfade gleich aus.
   Kein Default — der Aufrufer muss sich entscheiden.
3. **Login und Resend teilen sich EIN Widget.** Beide Aktionen leben auf
   derselben Maske; zwei Widgets untereinander wären für den Nutzer ein
   doppeltes Rätsel. Das Token ist einmalig gültig ⇒ nach jedem verbrauchten
   Token (Login-Fehlschlag, Resend, erfolgreicher Login mit folgender
   MFA-Stufe) wird per Nonce-Remount neu gestellt. Das Widget trägt
   `action="login"`; der Resend-Knopf wird gesperrt, solange kein Token da ist.
4. **Unverändert ohne Site-Key.** Die Optionen werden wie in #558 per Spread
   weggelassen, nicht auf `undefined` gesetzt — die Aufrufe bleiben bei
   deaktiviertem Captcha byte-identisch (Bestandstests prüfen das mit
   `toHaveBeenCalledWith({email, password})` bzw. `not.toHaveProperty`).
5. **i18n:** `auth.signup.captcha.*` wird zu `auth.captcha.*` (Wortlaut
   unverändert) — die Meldungen gelten jetzt für vier Pfade, nicht nur Signup.

## Arbeitsschritte

1. `features/auth/lib/captcha.ts` + `captcha.test.ts` (pure Funktionen).
2. `features/auth/lib/use-captcha.ts` (Hook).
3. `TurnstileWidget`: `action`-Prop, Test nachziehen.
4. `SignupPage` auf lib + Hook umstellen (Verhalten unverändert).
5. `session-context.ts` + `SessionProvider.signIn`: optionales `captchaToken`.
6. `LoginPage`: Widget, Token am Login und am Resend, Captcha-Fehlermeldung.
7. `ResetPasswordPage`: Widget + Token.
8. i18n de/en.
9. Doku zurücknehmen: `docs/signup-and-invites.md` §3 und
   `deploy/hetzner/supabase/.env.example`; CHANGELOG-Eintrag (Unreleased).
10. DoD lokal auf Node 22: `npm run lint`, `npx tsc -b`,
    `npm run test:coverage`, `npm run build`, `npm run license:check`.

## Fertig heißt

Mit gesetzten Captcha-Variablen funktionieren Signup, Login, Resend und
Passwort-vergessen; ohne gesetzte Variablen ist das Verhalten unverändert
(je ein Test pro Pfad für beide Richtungen).
