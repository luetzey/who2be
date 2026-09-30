- Activating a version despite failed or missing test cases now asks for a
  reason (learning loop B5, design spec S11, ADR-0053 6.3, part B).

  When the status bar knows the version's test report, "Activate" stays a
  single click if every test case passed (with the note "All n test cases
  passed. Activating is still your decision.") or if there are none. If any
  test case failed, errored or has no result — or the report cannot be
  loaded — the button reads "Activate…" and opens a dialog that lists the
  open test cases (icon, word, title, `k/n`) and requires a reason
  (1 to 1,000 characters after trimming). "Activate anyway" sends the
  transition with `acknowledge_test_report: true` and `override_reason`; the
  server's 409 answers `test_results_incomplete` and
  `test_override_reason_required` are explained inside the dialog. Members
  who are not admins see the disabled button with the visible reason "Only
  admins can activate." The five `transition*Version` client methods accept
  the optional contract fields. The detail pages switch this on in a
  follow-up change (part C).
