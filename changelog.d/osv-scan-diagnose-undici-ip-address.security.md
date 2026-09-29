- Web development dependencies updated to close three advisories published on
  2026-09-28: `undici` 6.28.0 → 6.29.0 (GHSA-3wwx-pv8p-q78v, denial of service
  in WebSocket permessage-deflate decompression) and `ip-address` 10.5.0 →
  10.7.2 (GHSA-2vr4-cq9g-pvrc, GHSA-rpw4-54j3-4h4q, incomplete address
  classification enabling SSRF). Both packages are dev-only and reach the
  shipped bundle through no path; the update is a lockfile-only change within
  the declared semver ranges. The nested `undici` copy under `jsdom` moved from
  8.10.2 to 8.11.2 along with it.

  The OSV scan in CI now reports what it finds. GitHub runs `run:` steps under
  `bash -e`, which `set -uo pipefail` does not switch off, so the scanner's exit
  code 1 — its normal signal for "findings" — ended the step before the list and
  the step summary were written: the job failed without naming a single
  package. The exit code is now captured explicitly; the gate itself is
  unchanged and still fails on any finding.
