# Cloud-Auth: Sign in with Apple anbinden

Karte `t_41742af8` · Vorgaenger `t_ce4d9a7f` (PR #631) · Branch
`who2be/t_41742af8-cloud-auth-sign-in-with-apple-anbinden-o`

## Outcome

Sign in with Apple ist als dritter externer Provider **in der Cloud-Edition**
anwaehlbar; Self-Hosting sieht die Schaltflaeche nicht. Die fuenf
Apple-Besonderheiten sind an der Quelle geprueft (Befunde als Kartenkommentar,
2026-09-25) und die Portal-Schritte samt Secret-Ablauf dokumentiert.

## Grundlage (nicht neu ermittelt)

- Edition-Merkmal: bestehendes `VITE_WHO2BE_EDITION` → `__CLOUD_BUILD__`
  (ADR-0029). **Kein zweiter Schalter.**
- Redirect-URI-Muster prod: `https://supabase.<DOMAIN>/auth/v1/callback`.
- Provider sind ueberall **env-gesteuert** mit Default `false`; die
  Cloud-Eigenschaft wird dort gesetzt, wo Credentials existieren (Hetzner-/
  Dokploy-`.env`), nie hart im Compose.
- Changelog: Fragment unter `changelog.d/`, **nie** `CHANGELOG.md`.

## Belegte Befunde (Kurzfassung, Details im Kartenkommentar)

1. GoTrue v2.196.0 kann Apple (`conf/configuration.go:524`,
   `api/external.go:613`, `api/settings.go:51`). Pflichtvariablen:
   `GOTRUE_EXTERNAL_APPLE_{ENABLED,CLIENT_ID,SECRET,REDIRECT_URI}`
   (`ValidateOAuth`, configuration.go:1337). `_URL` wird ignoriert.
2. Client Secret ist ein ES256-JWT, max. 15777000 s ≈ 6 Monate. GoTrue
   erneuert es **nicht** und warnt nicht; nach Ablauf antwortet Apple
   `invalid_client`, GoTrue macht daraus eine generische 500
   (`external_oauth.go:120`) ⇒ **stiller Ausfall**, Doku-Pflicht.
3. Name/E-Mail nur beim ersten Login — GoTrue fängt das selbst ab
   (`external_oauth.go:129-138` + `apple.go:169`). Unsere Seite: kein
   Handlungsbedarf.
4. Private Relay bricht nichts (Billing `router.py:145`, Mollie
   `email: str | None`, keine Domain-Filter im Repo). **Zwei Doku-Punkte:**
   Einladungs-Abgleich (`invitation_service.py:115`) schlaegt fehl, wenn die
   Relay-Adresse von der Einladungsadresse abweicht (kein neuer Fehler);
   Absender-Domain muss im Portal mit SPF/DKIM registriert sein, sonst
   bouncen Mails an Relay-Adressen.
5. Apple erlaubt kein `localhost`/keine IP, verlangt HTTPS ⇒ **lokal nicht
   testbar**, nur via oeffentlichem Tunnel mit registrierter Domain.

## Entscheidung (begruendet, kein zweiter Schalter)

Apple-Schaltflaeche nur im Cloud-Bundle, via `isAppleAuthEnabled()` im
bestehenden Modul `features/auth/lib/password-auth.ts` — spiegelbildlich zu
`isPasswordAuthEnabled()`, gleiche Begruendung (Literal-Replacement ist in
Vitest nicht stubbar). Grund: Apple verlangt Developer-Konto + registrierte
HTTPS-Domain; im Self-Hosting hat niemand beides, die Schaltflaeche waere dort
tote Flaeche. Google/GitHub bleiben in beiden Editionen unangetastet.

## Schritt 1 — Anbindung (PR sofort danach)

| # | Datei | Aenderung |
|---|---|---|
| 1 | `apps/web/src/features/auth/lib/password-auth.ts` | `isAppleAuthEnabled()` |
| 2 | `apps/web/src/features/auth/components/OAuthButtons.tsx` | `AppleGlyph`, Provider-Typ `'apple'`, Button gated |
| 3 | `apps/web/src/i18n/locales/{de,en}.json` | `auth.oauth.apple` |
| 4 | `docker-compose.yml` | 4x `GOTRUE_EXTERNAL_APPLE_*`, Default aus |
| 5 | `deploy/hetzner/supabase/docker-compose.yml` | dito, Redirect prod-Muster |
| 6 | `deploy/dokploy/docker-compose.yml` | dito |
| 7 | `.env.example` + `deploy/hetzner/supabase/.env.example` | Apple-Block |
| 8 | `apps/web/src/features/auth/pages/cloud-auth.test.tsx` | Tests analog Google/GitHub |
| 9 | `changelog.d/cloud-auth-apple.added.md` | Fragment |

Verifikation lokal: `npm run lint`, `npx vitest run` (auth), `npm run build`
fuer beide Editionen + Gate im Minifikat pruefen.

## Schritt 2 — Doku (eigener Commit, gleicher Branch)

`deploy/hetzner/supabase/README.md`: Portal-Schritte (App ID → Services ID →
Key), welcher Wert wohin, Secret-Ablauf + Erneuerungs-Pflicht, Redirect-URI-
Regeln/lokale Entwicklung, Private-Relay-Folgen (Einladung, SPF/DKIM).

## Out of Scope

Google/GitHub anfassen. Portal-Eintraege anlegen (macht der Owner). Den
Einladungs-E-Mail-Abgleich lockern.
