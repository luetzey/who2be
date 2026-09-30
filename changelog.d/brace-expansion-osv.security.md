- Web development dependency `brace-expansion` updated to close three
  denial-of-service advisories in its pattern parser (GHSA-6j4f-fj2g-mc7p,
  GHSA-q2hr-2g5m-vwhr, GHSA-qhr7-859c-m2p7): the eight nested 5.x copies move
  from 5.0.9 to 5.0.12, the top-level 1.x copy from 1.1.18 to 1.1.21. All copies
  are dev-only (ESLint, glob, npm tooling) and reach the shipped bundle through
  no path. The update is a lockfile-only change within the declared semver
  ranges; no overrides or scanner exceptions were added.
