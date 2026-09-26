- New `docs/cloud-erstinbetriebnahme.md`: the owner's first-run preparation
  list for the cloud edition, ordered by **lead time** rather than by
  importance, so the one item that takes days (Mollie account verification)
  comes first and the two-minute ones come last.

  It deliberately duplicates no procedure — provisioning commands stay in the
  Hetzner runbook, bring-up in `deploy/hetzner/README.md`, the acceptance
  journey in `docs/cloud-prod-smoke.md`. What it adds is what was previously
  written down nowhere: what to procure before day one, the exact OAuth
  redirect URI (`https://supabase.<DOMAIN>/auth/v1/callback`, identical for
  both providers and not guessable), which secrets must be identical across the
  two `.env` files, and the ordering constraints — the own user UUID only
  exists after the first signup, and the billing override needs a verified TOTP
  factor plus an `aal2` web session.

  It also answers the SMTP question that three documents left open: with the
  cloud edition's external-only sign-in, GoTrue confirms an account created
  from a provider identity with a verified email by itself, so a solo test run
  needs no mail provider at all. Team invitations still do, but they are not
  part of the test run.
