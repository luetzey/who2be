- **Watchdog server stack for monitoring (ADR-0062, package A1).** The new
  `deploy/monitor/` holds a separate Compose stack for a second, small server
  that watches production from the outside: GlitchTip (error tracking via the
  Sentry SDKs, own Postgres on an internal network only), Uptime Kuma (external
  checks, TLS expiry, push monitor for the backup heartbeat) and the Beszel hub
  (host and container metrics; the agent runs on production as a systemd
  service that connects outbound only). Every service carries the same
  hardening as production (log cap, `no-new-privileges`, `mem_limit`), images
  are pinned by digest, secrets come only from the environment, and only Caddy
  publishes ports. `apps/api/tests/test_monitor_compose.py` keeps this from
  drifting.

  The operator runbook gained the section "Waechter-Server (Monitoring,
  ADR-0062)" with a numbered setup list for the owner, the alert routes
  (Telegram for urgent alerts, mail for everything) and an acceptance test for
  each of them. The first start leaves Caddy out: all admin accounts are
  created through an SSH tunnel, and only then are the interfaces published,
  followed by an outside check that no setup or sign-up is still open. The
  record of processing activities (`docs/compliance/vvt.md`)
  adds V24 and a 30-day retention for error events, enforced by GlitchTip
  itself. The production Compose files and Caddyfile are unchanged; the SDKs
  that send error events follow in packages A2/A3.
