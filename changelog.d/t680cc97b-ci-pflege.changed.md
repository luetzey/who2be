- Every job in the CI workflow now carries a `timeout-minutes` limit instead
  of GitHub's 360-minute default. A hung job previously held the `main`
  concurrency group for up to six hours, and every push in that window lost its
  CI verdict (one documented case: a stuck Playwright browser install in `e2e`).
  The limits are derived from the last 30 successful `main` and 30 successful
  pull-request runs (2026-10-11…2026-10-16; 52–60 samples per job): the
  larger of the value proposed in issue #849 and twice the measured maximum
  rounded up to 5 (minimum 10) — `python` 40, `web` 30, `e2e-billing-cloud` 25,
  `e2e` and `e2e-mobile` 20, `compose-smoke` and `audit` 15, all others 10.
  `all-green` already treats `cancelled` as red, so a timeout fails the
  required check instead of passing it.
- The comment above the CI `concurrency` block no longer claims that `main`
  runs keep their result through a `run_id` group; no such group exists. It
  now describes what the code does — one group per pull request or ref,
  `cancel-in-progress` evaluating to false on `main` — and notes the measured
  case in which the middle of three `main` pushes within about two minutes ends
  as `cancelled` without a single job. Workflow behaviour is unchanged.
