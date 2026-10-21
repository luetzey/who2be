- Web dev dependencies `vitest`, `@vitest/mocker` and `@vitest/coverage-v8`
  raised to 4.1.12 to close GHSA-qxg6-89mg-rqv8 and GHSA-xp26-3454-mjgp in
  `@vitest/mocker` 4.1.11; all `@vitest/*` packages now resolve to a single
  4.1.12 copy. `vite` raised from 8.3.1 to the 8.3.x line (resolves to 8.3.5)
  because the same OSV scan reported six advisories against 8.3.1 that are
  fixed in 8.3.3 (GHSA-587h-7wmj-h5pm and five more). Both are dev-only and
  not part of the shipped bundle's runtime code; no major version changed
  and no scanner exception was added. The time-boxed exception for
  GHSA-ch52-4w7c-c8xp stays unchanged.
