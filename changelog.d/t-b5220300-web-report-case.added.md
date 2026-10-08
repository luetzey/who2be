- Cases can now be reported from the agent detail page (learning loop D6a,
  ADR-0053 3.3).

  "Report a case" opens a dialog with four everyday questions: what the
  situation was, what the agent did, what was expected and, optionally, what
  the impact was. Each question carries a help sentence. "Add details" holds
  the severity (preselected "Annoying" = `medium`) and a free-text link to the
  run or result. The kind "Went well – keep it" sends `signal=helpful` and
  asks "What should stay this way?" instead. Validation runs on submit and
  moves focus to the first invalid field; a character counter appears from
  80 % of a field's limit (situation and behaviour 4 000, expectation and
  impact 2 000, link 500, as in `CaseCreate`). Closing with input asks
  "Discard your input?"; nothing is stored locally. On error the input stays
  and an alert explains it, with its own text for a deleted agent. Reporting
  does not assign elements (decision Q2), and element pages keep "Give
  feedback". Below `md` the same dialog opens for now; the dedicated mobile
  page follows separately.

  The web client mirrors the case API: `createCase`, `listCases` (reads the
  next-page cursor from `X-Next-Cursor` and accepts several statuses),
  `countCases`, `getCase`, `deleteCase`, `transitionCase` and
  `putCaseElements`.
