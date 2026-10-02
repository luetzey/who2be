- The OSV scan of the web lockfile now carries a time-boxed exception for
  GHSA-ch52-4w7c-c8xp (`http-cache-semantics` 4.2.0, no fixed release yet),
  recorded in `apps/web/osv-scanner.toml` and valid until 2026-11-02. The
  package is dev-only and reaches the build solely through the CI license
  checker (`license-checker-rseidelsohn` via npm's fetch stack); it is not part
  of the shipped web bundle. The exception covers exactly this one advisory ID:
  the scan stays blocking for every other finding, and it turns red again for
  this one once the date passes, so the decision is re-made with current data.
