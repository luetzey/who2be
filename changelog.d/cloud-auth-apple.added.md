- **Sign in with Apple** is now available in the cloud edition, alongside Google
  and GitHub. The Apple button shows up only in the cloud build, gated by the
  edition flag that already exists (`VITE_WHO2BE_EDITION` → `__CLOUD_BUILD__`,
  ADR-0029 — no second switch). Self-hosting keeps Google and GitHub and does
  not show the Apple button, because Apple requires a paid Developer account
  *and* a domain registered in Apple's portal; the button would be dead space
  in a self-hosted stack. GoTrue is configured through
  `GOTRUE_EXTERNAL_APPLE_{ENABLED,CLIENT_ID,SECRET,REDIRECT_URI}`, all four
  defaulting to off/empty in every compose file — the credentials belong in the
  deployment's `.env`, not in a compose overlay.

  **Apple differs from the other two providers in ways that will bite you if
  you treat it the same.** All of the following was verified against GoTrue
  v2.196.0's source and Apple's documentation, not assumed:

  - **The client secret expires.** It is not a static string but an ES256 JWT
    signed with a `.p8` key, and Apple rejects any secret whose expiry is more
    than 15 777 000 seconds (six months) away. GoTrue treats the value as an
    opaque string: it neither generates nor renews it, and it does not warn as
    the date approaches. Once it lapses, Apple answers `invalid_client` and
    GoTrue turns that into a generic 500 — **Apple sign-in fails silently while
    Google and GitHub keep working**. Put the expiry date in a calendar; the
    renewal procedure is in `deploy/hetzner/supabase/README.md`.
  - **Name and email arrive only on the very first sign-in**, in a POST field
    that later sign-ins omit entirely. GoTrue handles this itself and stores
    them in the user metadata on that first pass, so nothing in Who2Be needs to
    change — but there is also no second chance to collect them.
  - **Private Relay addresses work.** Users may hide their real address, in
    which case an `@privaterelay.appleid.com` address arrives. Invoicing accepts
    it (Mollie treats the email as optional anyway) and nothing in Who2Be
    filters email domains. Two consequences to know about: a pending team
    invitation still has to be accepted from the address it was sent to, so
    someone invited at a work address who then signs in with a relay address is
    rejected — the same as signing in with a different Google account than the
    one invited. And any domain you send mail *from* must be registered with
    SPF/DKIM in Apple's portal, or mail to relay addresses bounces.
  - **Apple's redirect URI rules are stricter than Google's**: HTTPS only, a
    real domain name, no `localhost`, no IP address, no fragment. **Apple
    therefore cannot be exercised against a local stack** without a public
    HTTPS tunnel whose domain is registered in the portal — the same constraint
    the Mollie webhook already has.

  `deploy/hetzner/supabase/README.md` walks through what to create in the Apple
  Developer portal (App ID, Services ID, private key), which value goes where,
  and when the secret expires. Because Apple hands out a `.p8` key rather than a
  secret string, `scripts/gen_apple_client_secret.py` signs the JWT for you and
  prints its expiry date — so the value that belongs in your calendar comes out
  of the same command that produces the secret, and your signing key never has
  to go through a third-party generator.
