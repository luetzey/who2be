- The skip-budget gate (`scripts/ci/assert_skips_within_budget.py`) no longer
  asks "did pytest run at all?" when the JUnit XML is missing. The script also
  guards the Vitest suite in the `web` job, where that question sent diagnosis
  into the wrong stack. The message now names the missing path and asks whether
  the preceding test run wrote it; exit code (2) and budgets are unchanged, and
  a new test pins all exit paths.
- The cloud-session setup hook (`scripts/install_pkgs.sh`) now removes an
  existing `apps/web/node_modules` before `npm ci`, so every session starts
  from a clean tree instead of installing over a previous one (issue #959:
  lint and type check passed while `npm run test:coverage` failed to load
  Vitest's native Rolldown binding, npm/cli#4828). If the web install fails,
  the hook now prints a warning naming the affected command; it still never
  aborts the session.
