- New tests are now checked for whether they exercise behaviour. A test that
  reads a file and asserts a string in it stays green as long as the text is
  there — even when the thing the text describes does not work. This error type
  occurred three times in one day and passed every existing check twice; in one
  case thirteen existing test cases could not, in principle, catch a truncated
  database dump.

  The check runs in CI against newly added Python tests and **reports without
  blocking**: it was measured against 80 commits of real history before being
  wired up, and roughly a fifth of its hits are legitimate string tests
  (documentation-drift guards, golden-file contracts). A gate that blocks on day
  one is switched off by day three. Tests that are rightly text checks carry a
  justified exemption marker next to them; the rule, the exemption path and the
  measurement are documented in `docs/effectful-tests.md`.
