- The Hetzner production stacks now keep HTTP access logs and cap what every
  container may consume. Caddy writes an access log for all four subdomains to
  a dedicated volume, so the records survive a redeploy and sit on the
  container host rather than inside the container (BSI IT-Grundschutz
  SYS.1.6.A7, a basic requirement: storing container logging data "MUSS
  ausserhalb des Containers, mindestens auf dem Container-Host, erfolgen").
  Rotation is part of the same configuration — roughly 10 MiB per file, ten
  compressed generations, and a 14-day ceiling — so the log cannot fill the
  disk and the retention period needs no separate cleanup job that could fail
  silently.

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
