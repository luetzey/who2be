- The Hetzner production stacks now keep HTTP access logs and cap what every
  container may consume. Caddy writes an access log for all four subdomains to
  a dedicated volume, so the records survive a redeploy and sit on the
  container host rather than inside the container (BSI IT-Grundschutz
  SYS.1.6.A7, a basic requirement: storing container logging data "MUSS
  ausserhalb des Containers, mindestens auf dem Container-Host, erfolgen").
  Rotation is part of the same configuration — roughly 10 MiB per file and ten
  compressed generations from Caddy's own size-based rotation — so the log
  cannot fill the disk. The 14-day retention period is enforced separately, by
  a nightly host cron running `deploy/hetzner/scripts/rotate-access-log.sh`:
  the Caddy directives cap size rather than age, so on their own they would not
  hold the period. That script is the only deletion path for the period;
  Caddy's `roll_keep_for` only covers the generations Caddy itself creates and
  is not a fallback for it. Each part of the script fails independently and
  visibly — a night without a single request leaves no active file to rotate,
  which must not stop the deletion — and only a successful run writes its
  timestamp, so a cron that never ran is distinguishable from one that had
  nothing to do. The runbook documents the cron, why a restart rather than a
  signal is needed, and a quarterly check that starts from that timestamp. The
  behaviour is covered by an executable test that runs the rotation against
  real directories in the real Caddy image.

  Access logs carry IP addresses and user agents, a processing activity the
  record of processing activities already lists (V12, Art. 6(1)(f)); what it
  lacked was a retention period, and the 14 days now fill that placeholder in
  `docs/compliance/vvt.md` §7 and `docs/compliance/data-retention-and-erasure.md`
  §5. Credential headers stay redacted (Caddy's default, left on), and the
  OAuth-bearing query parameters on the API subdomain are replaced before a
  line reaches disk.

  Every service in both stacks additionally gained `no-new-privileges`, which
  covers the privilege-gain aspect of SYS.1.6.A17 — the requirement's scope is
  broader, so the measure is recorded as a contribution to A17 rather than as
  conformance with it. Docker-side log rotation and a memory ceiling sized for
  the target host came with it (SYS.1.6.A15; the runbook documents what happens
  when a ceiling is hit, as the requirement asks). A test holds all three
  across every service so a newly added one cannot slip through without them.
