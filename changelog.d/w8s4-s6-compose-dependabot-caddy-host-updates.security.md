- Container images used by the production stacks are now covered by automated
  dependency updates, and the reverse proxy moved to a current release. Four
  Dependabot ecosystems were already configured and a hard CVE gate runs in CI,
  but both look at Dockerfiles and language packages; the images that actually
  carry the deployment — Caddy, Postgres, GoTrue, nginx, Redis, SeaweedFS — are
  pinned in Compose files, which no ecosystem read. The `docker-compose`
  ecosystem now covers all four directories that hold such a pin (repository
  root, `deploy/dokploy`, `deploy/hetzner/supabase`, `deploy/hetzner/who2be`).
  Completeness is the point rather than a detail: partial coverage would be
  worse than none, because the files left out would count as checked. A test
  therefore counts the repository's Compose files against the configured
  directories in both directions, so neither a newly added stack nor a path
  pointing nowhere passes silently. Major bumps of the data-holding images stay
  out of automatic pull requests — a Postgres major needs `pg_upgrade` or a
  dump/restore, a GoTrue major runs auth migrations during startup.

  Caddy moved from 2.8.4 (May 2024) to 2.11.4, closing a two-year gap to the
  maintained line. The version jump is the risky part of this change, because a
  reverse proxy that misreads a directive keeps running and simply serves
  different headers, so it was verified before the pin moved rather than after:
  `caddy adapt` produces byte-identical configuration JSON for this Caddyfile
  in both versions, `caddy validate` passes in both, and `test_headers.sh` runs
  green against both images — nine security headers, the four differentiated
  content security policies, and the two status-code assertions. The published
  advisories for 2.11.1 were checked against this configuration rather than
  adopted wholesale: five of the six concern features this Caddyfile does not
  use. The sixth touches path matching, which this configuration does rely on
  for the single access decision it makes at the proxy — the internal area of
  the API — so both versions were exercised against that rule with a range of
  differing spellings of the same path, answered by a backend that deliberately
  replies there, so that a refusal is attributable to the proxy rather than to
  chance. Both versions behave identically, so the jump changes nothing at that
  point in either direction. The behaviour does depend on spelling, though, and
  how a proxy prepares a request before comparing it against a rule is
  implementation behaviour that is allowed to change between releases; an access
  decision should not rest on it. The rule therefore now also covers alternative
  notations of the same area, while paths that merely start with the same word
  continue through, and a new check runs that comparison against a live image so
  the question gets asked again at every future version jump rather than once.
  The documented outcome of the review is that the jump closes the version gap;
  it is not a fix for a demonstrated hole. Two
  behavioural differences are recorded in the runbook: 2.11 adds a `Via`
  response header naming the proxy hop, and the file log writer now honours
  `roll_at` and `mode`, which 2.8 discarded silently. Neither changes the
  retention period, which continues to be carried by the documented host cron.

  The runbook gained the matching operator procedures. Raising the Caddy
  version is now its own section with the pre-deploy header check, the
  advisory review, the deployment steps, four verification commands and the way
  back. Host-level updates are covered for the first time: kernel and OpenSSL
  live outside every container image and so outside every mechanism this
  repository has, and `unattended-upgrades` is now a provisioning step
  restricted to security sources, with a reboot confined to a maintenance
  window and a note on what changes when the encrypted volume is in use. The
  SSH configuration is no longer left to the base image but set explicitly as a
  drop-in and, more importantly, made checkable: the runbook gives the command
  that reports the effective state as the daemon sees it, since reading the
  configuration file answers a different question. Results for both go into a
  new evidence table, because neither setting is visible from a running system
  — key-based login works just as well with password login left open, and an
  unpatched host runs just as reliably as a patched one.
