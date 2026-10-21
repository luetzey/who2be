- Web dev dependencies `vitest`, `@vitest/mocker` and `@vitest/coverage-v8`
  raised to 4.1.12 to close GHSA-qxg6-89mg-rqv8 and GHSA-xp26-3454-mjgp in
  `@vitest/mocker` 4.1.11; all `@vitest/*` packages now resolve to a single
  4.1.12 copy (`chai` follows from 6.2.2 to 6.3.0 via `@vitest/expect`).
  Dev-only, not part of the shipped bundle; no major version changed and no
  scanner exception was added. The time-boxed exception for
  GHSA-ch52-4w7c-c8xp stays unchanged.
