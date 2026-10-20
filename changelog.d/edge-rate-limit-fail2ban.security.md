- Edge rate limit for the Hetzner stack (#540): a fail2ban filter and jail
  template under `deploy/hetzner/fail2ban/` read Caddy's existing JSON access
  log and ban an IP via the `DOCKER-USER` chain once it piles up rejected
  requests — before its flood reaches any container. No custom Caddy image and
  no second log; the in-app limits are unchanged.

  Two jails: `who2be-caddy-auth` counts failures on the sign-in and token
  routes (GoTrue `/auth/v1/token|signup|recover|otp|magiclink|verify|resend`,
  OAuth `/oauth/token|register|authorize`; 10 in 10 min → 1 h ban), and
  `who2be-caddy-edge` counts 401/403/429 across `api.<DOMAIN>` (120 in 2 min →
  15 min ban). `mcp.<DOMAIN>`, `/v1/health`, 404 and 5xx are never counted.

  The jail is a template the operator installs on the host; nothing is
  deployed automatically. Setup, checking (`fail2ban-client status`),
  unbanning and switching off are in `deploy/hetzner/RUNBOOK.md` §Rate-Limit an
  der Kante. `deploy/hetzner/tests/test_fail2ban_filter.sh` runs the real
  `fail2ban-regex` against lines written by Caddy 2.11 in the `compose-smoke`
  CI job, covering hits, non-hits, header injection and the ban chain.
