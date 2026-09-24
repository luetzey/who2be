- The cloud edition now signs people in through external providers only
  (Google, GitHub). Its login and registration pages show the provider buttons
  and nothing else: no email/password fields, no "stay signed in", no "forgot
  password", and `/reset-password` redirects to the login page rather than
  offering a form that leads nowhere. GoTrue backs this up with
  `GOTRUE_EXTERNAL_EMAIL_ENABLED=false`, which rejects `POST /signup` and
  `POST /token?grant_type=password`.

  **Self-hosting is untouched.** The switch is the edition flag that already
  exists (`VITE_WHO2BE_EDITION` → `__CLOUD_BUILD__`, ADR-0029) plus a GoTrue
  environment variable that still defaults to `true`; no sign-in code was
  removed and the registration page still exists. Flipping either one back
  restores password login.

  The registration page deliberately stays reachable in the cloud instead of
  redirecting to the login: it carries the mandatory terms-and-privacy consent
  that gates the provider buttons, and a redirect would have removed the only
  consent gate in the sign-up flow.

  Team invitations are unaffected — GoTrue v2.196.0 checks the email-provider
  flag only in `POST /signup`, `POST /token?grant_type=password` and
  `POST /magiclink`, not in `POST /invite`, `POST /verify`, `POST /recover` or
  `PUT /user`. **A cloud deployment therefore still needs SMTP**, for team
  invitations and email-address changes; only the sign-up confirmation and
  password-reset mails go away. `deploy/hetzner/supabase/README.md` documents
  the OAuth variables and the exact redirect URI to register with each
  provider.
