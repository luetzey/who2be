- The OSV scan of the web lockfile now carries time-boxed exceptions for
  `glob` 13.0.6 and `minimatch` 10.2.5/10.2.6/3.1.5, recorded in
  `apps/web/osv-scanner.toml` and valid until 2026-11-30. Fixed releases
  exist only in new majors (`glob` 14.0.2, `minimatch` 11.0.1) that no parent
  package accepts yet; both packages are dev-only tooling and not part of the
  shipped web bundle. The exception for `http-cache-semantics`
  (GHSA-ch52-4w7c-c8xp) was removed because the scan no longer uses it.
