# Fix: Admin-Aktionen fordern MFA trotz eingerichtetem TOTP

Stand: 2026-07-01 · Coder · Trigger „fix [X]" → Code-Task-Flow (kleiner Fix)

## Symptom

Nutzer richtet Zwei-Faktor (TOTP) ein, erhaelt bei Admin-Aktionen dennoch
403 `mfa_required`:

> Diese Admin-Aktion erfordert Zwei-Faktor-Authentifizierung (MFA). Richte in
> den Kontoeinstellungen einen TOTP-Faktor ein und melde dich anschliessend
> erneut an.

## Ursache (bestaetigt)

- Backend `core/security.require_aal2` (`apps/api/.../core/security.py:187`) ist
  **korrekt**: Admin-Aktionen verlangen eine `aal2`-Session.
- Das Enrollment (`apps/web/.../settings/components/MfaSection.tsx`) hebt via
  `challengeAndVerify` **nur die gerade aktive** Session auf `aal2`.
- Der Login-Flow (`SessionProvider.signIn` → nur `signInWithPassword`;
  `LoginPage.tsx`) hat **keinen MFA-Challenge-Schritt**. Sessions liegen im
  tab-lebensdauer-`sessionStorage` (`lib/supabase.ts`). Nach neuem Tab / Ablauf
  / erneutem Login ist die Session wieder `aal1` — und es gibt **keinen Weg
  zurueck auf `aal2`**. Jede Admin-Aktion 403t; der Rat „erneut anmelden" hilft
  nicht, weil der Login keine Challenge kennt.

## Fix (Frontend, in-place)

Login um einen Step-up-Challenge-Schritt erweitern (GoTrue-Kanon:
`getAuthenticatorAssuranceLevel` → `challenge` → `verify`).

1. **`auth/session-context.ts`** — `signIn`-Rueckgabetyp
   `Promise<{ mfaRequired: boolean }>` (die `vi.fn()`-Test-Mocks bleiben
   zuweisbar; kein Interface-Zwang auf 28 Test-Literale).
2. **`auth/SessionProvider.tsx`**
   - Helper `mfaStepUpPending()` (`getAuthenticatorAssuranceLevel`:
     `nextLevel === 'aal2' && currentLevel !== 'aal2'`; try/catch → `false`,
     damit ein getAAL-Fehler den Login nicht blockiert).
   - `apply()`: eine `aal1`-Session mit faelligem zweiten Faktor **nicht**
     committen (setSession null) — sonst landet der User mit `aal1` in der App.
     Autoritatives Gate gegen die onAuthStateChange-Race.
   - `signIn`: nach `signInWithPassword` `mfaStepUpPending` pruefen; wenn faellig
     → `{ mfaRequired: true }` ohne Commit; sonst wie bisher committen.
3. **`features/auth/pages/LoginPage.tsx`** — zweite Stufe: bei `mfaRequired`
   TOTP-Code-Feld zeigen; `supabase.auth.mfa.listFactors` → `challenge` →
   `verify` (analog `MfaSection`). Nach Erfolg committet `apply()` die
   `aal2`-Session; der reaktive `session !== null`-Guard navigiert.
4. **i18n** `de.json`/`en.json` — `auth.login.mfa.*`.

## Tests

- `SessionProvider.test.tsx`: `mfa`-Mock; Hold-back-Test (aal1+pending → keine
  Session committed).
- `LoginPage.test.tsx`: `mfa`-Mock; MFA-Flow (Code-Feld erscheint, `verify`
  aufgerufen).
- DoD: `npm run lint`, `npx tsc --noEmit`, `npm test`, `npm run build` gruen.

## Out of Scope

Backend-Gate, Enrollment-UI, andere Auth-Wege (OAuth/Magic-Link tragen `aal`
serverseitig). Kein Redesign des Session-Storage.
