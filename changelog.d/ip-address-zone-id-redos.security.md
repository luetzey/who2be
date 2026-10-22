- Web development dependency `ip-address` updated from 10.7.2 to 10.7.4 to
  close GHSA-rxp7-6hxx-x8q5 (published 2026-10-22, medium): parsing an IPv6
  address with a zone ID in `Address6` took quadratic time, a denial-of-service
  vector for untrusted input. The package is dev-only and reaches the shipped
  bundle through no path. Its only route is the license gate in CI
  (`license-checker-rseidelsohn` → `@npmcli/arborist` → `npm-registry-fetch` →
  `make-fetch-happen` → `@npmcli/agent` → `socks-proxy-agent` → `socks` →
  `ip-address`). The update changes only the lockfile and stays within the
  declared semver range. It turns the blocking OSV scan in CI green again.
