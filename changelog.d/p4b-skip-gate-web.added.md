- The `web` CI job now enforces the same skip budget as the `python` job. The
  coverage step writes a JUnit XML and `scripts/ci/assert_skips_within_budget.py`
  — the existing script, not a copy — fails the job when any test was skipped
  (budget **0**, matching the measured state of the full suite).

  The gate deliberately sits on the coverage step and **not** on the a11y step.
  `npm run test:a11y` runs the whole suite with `--testNamePattern a11y`, and
  Vitest reports every filtered-out test as `skipped`; that step therefore shows
  four-digit skip counts by construction, while the very same tests pass in the
  coverage run a minute earlier. A gate there would be permanently red.

  The reporter is configured per CLI flag on the step rather than in
  `apps/web/vite.config.ts`, because both Vitest steps share that config and a
  reporter there would also emit an XML for the a11y step — precisely the
  artefact that invites the misdiagnosis above. The script gained one
  backwards-compatible change: Vitest writes a bare `<skipped/>` with no
  attributes, so when no reason is present the test name is used instead of a
  repeated placeholder. The pytest path, which supplies `message`, is unchanged.
