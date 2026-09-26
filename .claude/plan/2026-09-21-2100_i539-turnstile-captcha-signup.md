# #539 — Captcha vor der Registrierung (Cloudflare Turnstile)

Branch: `wt/i539-turnstile` · Kanban: `t_a662079e` · Modus: **produktiv**
(`.claude/project.json` fehlt → der vorsichtigere Zustand gilt, kein Auto-Merge).

## Outcome

Vor der Selbstregistrierung steht optional ein Cloudflare-Turnstile-Captcha.
Ohne gesetzte Schluessel ist das Verhalten **exakt wie heute** — kein Widget,
kein Token, kein zusaetzlicher Netzwerk-Call. Einladungs- und Login-Pfad
bleiben unberuehrt.

## Pflichtschritt: Env-Namen gegen GoTrue v2.158.1 belegt

Der Auftrag verlangt ausdruecklich einen Beleg gegen die gepinnte Version
statt der Uebernahme aus `docs/cloud-hosting-owner-guide.md:350`.

Quelle: `supabase/auth` Tag **v2.158.1**,
`internal/conf/configuration.go` (gezogen per `curl`, 1005 Zeilen).

```go
// Zeile 423-427
type CaptchaConfiguration struct {
	Enabled  bool   `json:"enabled" default:"false"`
	Provider string `json:"provider" default:"hcaptcha"`
	Secret   string `json:"provider_secret"`
}

// Zeile 495-496 — Captcha haengt unter Security, OHNE split_words
type SecurityConfiguration struct {
	Captcha CaptchaConfiguration `json:"captcha"`
	...
}

// Zeile 257 — Security haengt unter der globalen Konfiguration
Security SecurityConfiguration `json:"security"`

// Zeile 653 — envconfig-Praefix
envconfig.Process("gotrue", config)
```

`envconfig` (kelseyhightower) bildet verschachtelte Structs auf
`PRAEFIX_FELD_FELD` ab; ohne `split_words` bleibt der Feldname ungetrennt.
Daraus folgen **genau drei** Variablen:

| Variable | Werte | Default |
|---|---|---|
| `GOTRUE_SECURITY_CAPTCHA_ENABLED` | `true` / `false` | `false` |
| `GOTRUE_SECURITY_CAPTCHA_PROVIDER` | `turnstile` / `hcaptcha` | `hcaptcha` |
| `GOTRUE_SECURITY_CAPTCHA_SECRET` | Turnstile *Secret Key* | leer |

Das Secret-Feld heisst im JSON `provider_secret`, per Env aber
`..._CAPTCHA_SECRET` (envconfig nutzt den **Go-Feldnamen** `Secret`, nicht das
JSON-Tag). Genau hier waere eine Uebernahme aus dem Owner-Guide geraten
gewesen — `GOTRUE_SECURITY_CAPTCHA_PROVIDER_SECRET` existiert **nicht**.

Validierung (`configuration.go:429-445`): ist `Enabled=false`, wird gar nichts
geprueft → **leer gelassen = Verhalten unveraendert**, der Stack startet wie
bisher. Ist `Enabled=true`, muss der Provider `hcaptcha` oder `turnstile` sein
UND das Secret nicht leer, sonst bricht GoTrue beim Start ab.

Wirkungsbereich (`internal/api/api.go`, v2.158.1): `api.verifyCaptcha` haengt
an `/signup` (Z. 138), `/recover` (179), `/resend` (186), `/magiclink` (193),
`/otp` (200), `/token` (207), `/sso` (267). `middleware.go:164-190`:
Admin-Credentials ueberspringen die Pruefung, und `/token` nur beim
`grant_type=password`.

**Konsequenz fuer AK „Einladungs- und Login-Pfad unberuehrt":**
Der Invite-Versand laeuft ueber `POST /auth/v1/invite` mit dem
Service-Role-Key → Admin-Pfad → Captcha wird uebersprungen. Der
Invite-Magic-Link-Einloesepfad (`/verify`) traegt `verifyCaptcha` gar nicht
erst. **Aber:** aktiviertes Captcha wirkt auch auf den Passwort-Login
(`/token?grant_type=password`) und auf „Bestaetigungs-Mail erneut senden"
(`/resend`). Diese Wirkung ist eine Eigenschaft von GoTrue, nicht dieses PR;
sie wird dokumentiert, damit der Betreiber sie vor dem Einschalten kennt
(siehe Arbeitspaket 3).

## Muster-Entscheidung

**Gewaehlt: lokale Wrapper-Komponente ohne neue npm-Abhaengigkeit.**
`TurnstileWidget.tsx` laedt `https://challenges.cloudflare.com/turnstile/v0/api.js`
per Script-Tag nach und rendert das Widget explizit ueber die globale
`window.turnstile.render`-API.

Verworfen: `@marsidev/react-turnstile` (kompakter, ~4 Zeilen statt ~90). Gegen
die Abhaengigkeit entschieden, weil sie im Default-Fall (kein Site-Key) reiner
Bundle-Ballast waere, eine Lizenz-/Supply-Chain-Pruefung nach sich zieht
(OSS-License-Compliance) und das Widget selbst nur drei Aufrufe kennt
(`render`, `reset`, `remove`).

Beleg fuer die Variabilitaet: **keiner** — und genau deshalb bleibt die
Struktur flach. Es gibt einen Captcha-Anbieter (Owner-Entscheidung Turnstile,
hCaptcha explizit abgelehnt), also keine Provider-Abstraktion, kein Interface,
kein Strategy-Pattern. Das waere die unbelegte Abstraktion, vor der die
Design-Prinzipien warnen.

## Arbeitspakete

Bewusst **nicht** an Sub-Agents delegiert: die drei Code-Dateien haengen ueber
ein gemeinsames Config-Feld zusammen (`config.ts` → `SignupPage.tsx` →
`TurnstileWidget.tsx`), datei-disjunkte Pakete waeren hier nur scheinbar
disjunkt. Sequenziell in einem Lauf, Verifikation nach jedem Paket.

### AP1 — Deployment/Env (kein Code)
- `deploy/hetzner/supabase/.env.example`: die drei `GOTRUE_SECURITY_CAPTCHA_*`
  dokumentiert + auskommentiert, plus `WHO2BE_TURNSTILE_SITE_KEY` als Zeiger
  auf die Web-Seite.
- `deploy/hetzner/supabase/docker-compose.yml` + `deploy/dokploy/docker-compose.yml`:
  `auth`-Service bekommt die drei Variablen mit **leeren Defaults**
  (`${GOTRUE_SECURITY_CAPTCHA_ENABLED:-false}` usw.) → unveraendertes Verhalten.
- `deploy/dokploy/docker-compose.yml` + `deploy/hetzner/.env.example`:
  `WHO2BE_TURNSTILE_SITE_KEY` am `web`-Service durchreichen.

### AP2 — Web (Widget + Signup)
- `apps/web/docker/40-who2be-runtime-config.sh`: `turnstileSiteKey` in
  `/config.js` schreiben (leer = aus).
- `apps/web/src/config.ts`: Feld `turnstileSiteKey` (Runtime → `VITE_` → `''`).
- `apps/web/src/features/auth/components/TurnstileWidget.tsx` (neu).
- `apps/web/src/features/auth/pages/SignupPage.tsx`: Widget rendern, Token als
  `options.captchaToken` an `supabase.auth.signUp` geben, Submit bis zum Token
  sperren, Widget nach Fehler zuruecksetzen, GoTrue-Captcha-Fehler in eine
  verstaendliche Meldung uebersetzen.
- `apps/web/src/i18n/locales/{de,en}.json`: neue Keys unter `auth.signup.captcha`.
- Tests in `SignupPage.test.tsx` (aus/an/Fehlerfall).

**Nicht anfassen:** `LoginPage.tsx`, `SessionProvider.tsx`, alles unter
`features/invitations/`, jede Backend-Datei unter `apps/api/`.

### AP3 — Doku
- `docs/signup-and-invites.md`: neuer Abschnitt „Captcha bei der Registrierung"
  inkl. der Nebenwirkung auf Login/Resend.
- `docs/compliance/legal-texts-checklist.md` §2: Cloudflare als Empfaenger in
  der Tabelle + als Pruefpunkt (Drittland USA). **Akzeptanzkriterium.**
- `docs/cloud-hosting-owner-guide.md` L4: von „noch offen" auf „vorbereitet"
  mit den belegten Variablennamen.
- `CHANGELOG.md` Unreleased.

## Verifikation (lokal vor dem Push)

```
cd apps/web && npx tsc -b && npm run lint && npm run test
```

## Nicht im Scope

Turnstile-Konto/Schluessel anlegen (Owner). Captcha an Login oder
Passwort-Reset in der UI. Backend-seitige Captcha-Pruefung (macht GoTrue).
Der Wechsel von `WHO2BE_LAUNCH_MODE=coming_soon` auf `open`.
