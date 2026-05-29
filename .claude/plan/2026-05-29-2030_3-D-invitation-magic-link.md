# Plan: Phase 3-D — Invitation-Magic-Link + Onboarding-Bridge

- Datum: 2026-05-29
- Branch: `claude/blissful-allen-8CpKx` (Cloud-Praefix; Sub-Track-D)
- Vorbedingung: Track 0 gemerged (Status-Default, Models). Hier nicht relevant.
- Master-Plan: `2026-05-29-1900_phase-3-ux-polish.md` §Track D

## Ziel

GoTrue-Magic-Link-Flow fuer Einladungen: Mail enthaelt
`{WEB_BASE_URL}/invitations/{token}/accept?via=magic`. Nach Klick steht der
User dank GoTrue-Login bereits authentifiziert auf der Accept-Page; Auto-Accept
ohne weiteren Klick. Klartext-Token bleibt als manueller Fallback im 201-Body.

Zusaetzlich: Open-Redirect-Schutz auf `LoginPage` (`?next=`), Email-Mismatch-
Schutz auf Backend (JWT-Email vs. Invitation-Email).

## Scope

### Backend

1. `gotrue_mailer.build_accept_url(token)` → URL enthaelt jetzt
   `?via=magic`-Query. Klartext-Token-Fallback bleibt im 201-Body (Service
   unveraendert).
2. `core/security.py`:
   - `verify_supabase_jwt` zusaetzlich Email aus JWT-Claim lesen (optional —
     kann `None` sein, wenn der Token sie nicht traegt; Tests heute setzen
     keinen Email-Claim).
   - `CurrentPrincipal` um `email: str | None` ergaenzen.
3. `services/invitation_service.accept(token, user_id, jwt_email=None)`:
   - Wenn `jwt_email` gesetzt ist und nicht (case-insensitiv) der
     Invitation-Email entspricht → 403 mit Microcopy „Diese Einladung ist fuer
     eine andere Email-Adresse.". Bewusst keine state-Aenderung — die
     Invitation bleibt offen.
   - Implementierung: Repository-Accept zusaetzlich mit `expected_email`-
     Parameter und neuem `AcceptResult.status='email_mismatch'`. Check laeuft
     in derselben Transaktion vor der Mutation.
4. `routers/invitations.accept_router`: User-Dependency liefert Principal
   (mit Email) statt nur `UUID`; Email wird an Service weitergereicht.

### Frontend

5. `InvitationAcceptPage`:
   - `?via=magic` → Auto-Accept beim Mount (kein Button mehr). Microcopy
     „Du wirst angemeldet…" waehrend der Annahme. Bei Erfolg redirect ins
     Dashboard wie heute.
   - Ohne `?via=magic` → bestehender Flow (Button + Login-Redirect).
   - 403 → Microcopy „Diese Einladung ist fuer eine andere Email-Adresse."
6. `LoginPage`:
   - `next` muss mit `/` beginnen, nicht mit `//` (Open-Redirect-Schutz), und
     darf kein vollqualifizierter URL sein. Sonst Fallback auf `/`.

### Tests

7. Backend `test_invitations.py`:
   - `redirect_to`-URL-Format (Unit-Test gegen `gotrue_mailer.build_accept_url`).
   - Email-Mismatch → 403 (Integration-Test mit JWT, der einen Email-Claim
     traegt; Helper `_jwt` um optionalen `email`-Param erweitern).
8. Frontend `InvitationAcceptPage.test.tsx`:
   - `?via=magic` + eingeloggt → Auto-Accept ohne Klick.
   - manuell + nicht eingeloggt → Redirect (besteht heute).
   - 403 → Email-Mismatch-Microcopy.
9. Frontend `LoginPage.test.tsx`:
   - `next=//evil.com` wird ignoriert (Fallback `/`).

## Nicht in diesem PR

- Editor/Forms (Track B).
- Navigation (Track C).
- Backend-Endpoints ausser Invitation (Track A).

## DoD

- `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -q` gruen.
- `npm run lint && npx tsc --noEmit && npm test && npm run build` gruen.
- Commit `feat(api,web): Phase-3-D — Invitation-Magic-Link + Onboarding-Bridge` auf
  `claude/blissful-allen-8CpKx`, Push.
