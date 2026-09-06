# Admin-MFA-Pflicht (Zwei-Faktor fuer administrative Zugaenge)

> Stand: 2026-06-05 · Befund **S1** (`docs/security-findings-phase-2.md`) ·
> Arbeitspaket **WP-F** (`.claude/plan/2026-06-05-1311_compliance-de-saas-remediation.md`).

Administrative Aktionen in Who2Be erfordern eine **Zwei-Faktor-Session (MFA,
AAL2)**. Wer eine Admin-Mutation ohne verifizierten zweiten Faktor versucht,
erhaelt **403** mit dem Hinweis, MFA einzurichten. Diese Seite beschreibt, wie
das technisch erzwungen wird und was Betreiber/Admins tun muessen.

## Kurzfassung

- **TOTP-MFA ist in GoTrue aktiv** (Compose-Default, siehe unten). Nutzer richten
  einen Authenticator in den **Konto-Einstellungen → Sicherheit** ein.
- Nach einer verifizierten TOTP-Challenge traegt das Access-Token den Claim
  **`aal=aal2`**. Die API erzwingt `aal2` fuer jede Admin-Aktion zentral in
  `core/security.require_aal2` (an `require_role(ctx, admin)` gehaengt).
- **Admins MUESSEN** einen TOTP-Faktor einrichten — sonst sind Mitglieder-,
  Einladungs-, Workspace- und (Cloud-)Billing-Admin-Aktionen blockiert.

## Authenticator-Assurance-Level (AAL)

GoTrue/Supabase stuft die Sitzung nach dem Authentifizierungsstand ein:

| AAL | Bedeutung |
|-----|-----------|
| `aal1` | Ein Faktor (Passwort, Magic-Link, Social-Login). |
| `aal2` | Zusaetzlich eine verifizierte MFA-Challenge (TOTP). |

Der Wert steht als `aal`-Claim im JWT. Das Backend liest ihn in
`verify_supabase_jwt` aus und legt ihn in den `WorkspaceContext`.

## Backend-Gate (`core/security.py`)

`require_role(ctx, WorkspaceRole.admin)` ruft fuer administrative Aktionen
zusaetzlich `require_aal2(ctx)` auf. Damit erbt **jede** bestehende
Admin-Call-Site das Gate, ohne dass die einzelnen Router/Services es
duplizieren. `require_aal2` blockt mit **403**, wenn keine AAL2-Session
vorliegt — mit zwei bewussten Ausnahmen:

- **API-Token** (`is_api_token`): Maschinen-Pfad ohne MFA-Konzept (analog
  GitHub-PATs). Tokens werden separat ausgestellt und sind einzeln
  revozierbar, daher vom Gate ausgenommen. (MCP-Write-Tools, Promote/Retire,
  Cloud-Billing-Automatik bleiben funktionsfaehig.)
- **Fehlender `aal`-Claim** (`aal is None`): aeltere/handsignierte Test-JWTs
  tragen ihn nicht. Produktive GoTrue-JWTs setzen `aal` **immer**, daher
  greift das Gate in Produktion zuverlaessig; nur ein *expliziter*
  Nicht-aal2-Wert (typisch `aal1`) wird geblockt (**fail-open bei Absenz**).

Betroffene Admin-Aktionen (alle `require_role(ctx, admin)`):
- `members`: Rolle aendern, Mitglied entfernen,
- `invitations`: Einladung ausstellen/widerrufen, Pending-Liste,
- `workspaces`: Workspace umbenennen/loeschen,
- `billing` (Cloud): Checkout/Override (im JWT-Pfad).

## GoTrue-Konfiguration (TOTP aktivieren)

GoTrue **v2.158.1** kennt **kein** Top-Level `GOTRUE_MFA_ENABLED`; Faktoren
werden pro Typ geschaltet. TOTP ist default an und wird explizit gesetzt in:

- `docker-compose.yml` (dev) — Service `auth`,
- `docker-compose.cloud.yml` (Cloud-lokal) — vererbt aus dem Basis-`auth`,
- `deploy/hetzner/supabase/docker-compose.yml` (Prod) — Service `auth`.

Relevante Variablen (mit `.env`-Override):

```
GOTRUE_MFA_TOTP_ENROLL_ENABLED=true   # Enrollment erlauben
GOTRUE_MFA_TOTP_VERIFY_ENABLED=true   # Challenge/Verify erlauben
GOTRUE_MFA_MAX_ENROLLED_FACTORS=10    # max. Faktoren pro Nutzer
```

Vorlagen: `.env.example` und `deploy/hetzner/supabase/.env.example`.

## Enrollment (Nutzer-Flow)

In **Konto-Einstellungen → Sicherheit → Zwei-Faktor (MFA)**:

1. „Authenticator hinzufuegen" → die App ruft `supabase.auth.mfa.enroll`
   (`factorType: 'totp'`) und zeigt QR-Code + Klartext-Secret.
2. Authenticator-App (z. B. 1Password, Google Authenticator) scannt den
   QR-Code (oder das Secret manuell eingeben).
3. Den 6-stelligen Code eingeben → `supabase.auth.mfa.challengeAndVerify`.
   Nach Erfolg ist der Faktor verifiziert; die verifizierende Sitzung ist
   bereits `aal2`.

Faktoren lassen sich in derselben Sektion auflisten und entfernen
(`supabase.auth.mfa.unenroll`). **Hinweis:** Ohne verbleibenden Faktor sind
Admin-Aktionen wieder blockiert.

## Login-Step-up (Challenge bei der Anmeldung)

Ein reiner Passwort-Login liefert bei einem Account mit verifiziertem TOTP-
Faktor nur eine `aal1`-Sitzung (GoTrue meldet `nextLevel: 'aal2'`). Da die
Sitzung per Default in tab-lebensdauer-`sessionStorage` liegt, ist nach neuem
Tab, Ablauf oder erneutem Login ein Step-up noetig — sonst blieben
Admin-Aktionen blockiert. (Die opt-in-Ausnahme dazu steht weiter unten:
§"Angemeldet bleiben".)
Der Login-Flow erledigt das automatisch (`apps/web/.../auth/pages/LoginPage.tsx`
+ `auth/SessionProvider.tsx`):

1. Nach `signInWithPassword` prueft `SessionProvider` via
   `mfa.getAuthenticatorAssuranceLevel`, ob ein Step-up faellig ist. Wenn ja,
   wird die `aal1`-Sitzung **nicht** committed (kein Durchlassen in die App).
2. Die LoginPage zeigt ein TOTP-Code-Feld und fuehrt
   `mfa.challenge` + `mfa.verify` aus. Nach Erfolg traegt die Sitzung `aal2` und
   wird committed; der Nutzer landet an seinem urspruenglichen Ziel (`next`).

## "Angemeldet bleiben" — opt-in Session-Persistenz (Issue #430, ADR-0052)

Die Login-Seite traegt eine standardmaessig **nicht** gesetzte Checkbox
„Angemeldet bleiben ({{stunden}} h)". Sie aendert NICHTS am Step-up oben —
sie steuert nur, WO die (ggf. bereits `aal2`-gehobene) Session danach
persistiert wird:

- **Haken AUS (Default):** unveraendertes Verhalten. Die Session liegt in
  `sessionStorage` (Tab-Lifetime) — jeder neue Tab und jeder Browser-Neustart
  verlangt einen vollen Login inklusive TOTP-Step-up wie oben beschrieben.
- **Haken AN:** die Session liegt stattdessen in `localStorage` und
  ueberlebt neuen Tab + Browser-Neustart — **bis zu einer absoluten
  Obergrenze** (`WHO2BE_SESSION_MAX_AGE_HOURS`, Default 12 h, Bereich 1-24).
  Innerhalb dieser Frist entfaellt der Step-up in neuen Tabs (die Sitzung ist
  ja bereits `aal2`, falls sie das beim Login war). **Nach Ablauf der
  Obergrenze erzwingt `SessionProvider` beim naechsten Boot einen vollen
  `supabase.auth.signOut()`** (Refresh-Token wird serverseitig ungueltig) —
  der naechste Login durchlaeuft wieder den kompletten Flow oben, inklusive
  Step-up.
- **Reichweite der Obergrenze (wichtig fuer die Risiko-Einordnung):** Sie wird
  **clientseitig** durchgesetzt — `SessionProvider` vergleicht vor jedem
  Commit einer Session den Zeitstempel aus dem Marker `who2be.auth.remember`
  (`localStorage`) und ruft daraufhin selbst `signOut()`. Ein Marker, aus dem
  kein gueltiger Zeitstempel zu lesen ist, gilt dabei als abgelaufen
  (fail-closed). Fuer einen normalen Nutzer ist die Grenze damit nicht
  verlaengerbar. Sie ist aber **keine serverseitige Session-Lebensdauer**: wer
  Schreibzugriff auf den `localStorage` hat (erfolgreicher XSS) oder das
  Token-Paar aus dem Browser traegt, ist an diese Pruefung nicht gebunden — das
  Refresh-Token bleibt bis zu seiner GoTrue-eigenen Lebensdauer gueltig.
  `GOTRUE_JWT_EXP` und die Refresh-Rotation sind bewusst unveraendert
  (ADR-0052 §Konsequenzen). Eine echte serverseitige Kappung braucht den dort
  genannten Auth-BFF.
- **Logout meldet alle offenen Tabs ab:** `@supabase/auth-js` broadcastet
  `SIGNED_OUT` per `BroadcastChannel` an jeden gleichzeitig offenen Tab.
  Ein waehrend des Logouts **geschlossener** Tab merkt das erst beim
  naechsten Oeffnen — dort greift dann die Obergrenzen-Pruefung oben.
- Details/Abwaegung (insb. warum das die XSS-Betrachtung aus ADR-0035 nicht
  aufweicht): `docs/adr/0052-web-session-persistenz.md`.

## Betreiber-Empfehlung: Host-/Infra-Zugang

- **SSH zum Hetzner-Host** ist bereits key-only (siehe `deploy.yml`); kein
  Passwort-Login.
- Fuer die **Hetzner-Cloud-Konsole** (Web-Login des Betreiber-Accounts) wird
  **MFA dringend empfohlen** — sie ist der Out-of-Band-Zugang zur Infrastruktur
  und liegt ausserhalb der Anwendung. (Detailliertes Runbook: separat.)

## Tests

- Backend: `apps/api/tests/test_mfa_aal2.py` — Admin-Aktion mit `aal1` → 403,
  mit `aal2` → ok, fehlender Claim/Token → exempt; Rollen-Check hat Vorrang.
  `apps/api/tests/test_security.py::test_verify_jwt_reads_aal_claim`.
- Frontend: `apps/web/src/features/settings/components/MfaSection.test.tsx`
  (Enroll/Verify/Liste) + `MfaSection.a11y.test.tsx` (axe). Login-Step-up:
  `apps/web/src/auth/SessionProvider.test.tsx` (aal1+pending → kein Commit) +
  `apps/web/src/features/auth/pages/LoginPage.test.tsx` (Code-Feld + verify).
- "Angemeldet bleiben" (Issue #430): `SessionProvider.test.tsx` (Ablauf
  erzwingt Logout, Session innerhalb der Obergrenze wird committed,
  `signIn`/`signOut` setzen bzw. loeschen die Flags), `LoginPage.test.tsx`
  (Checkbox-Default, Remember-Flag nur mit Haken), `config.test.ts`
  (`resolveSessionMaxAgeHours`, Bereich 1-24, Fail-closed-Default) sowie
  `lib/supabase.test.ts` (delegierender Storage-Adapter, Cross-Tab-Logout-
  Vorbedingung). E2E-Journey (neuer Tab bleibt eingeloggt):
  `apps/web/e2e/journeys.spec.ts`.
