- The five detail pages (personas, playbooks, resources, external tools,
  system prompt templates) now show the version's test cases during review
  (learning loop B5, design spec S11, ADR-0053, part C).

  Opening the "Versions" tab expands the version that is in review; an explicit
  `?diff=<n>` link still wins. Next to its diff, the test case results of that
  version are loaded from `GET /versions/{entity_type}/{version_id}/test-report`.
  The empty state links to the "Test cases" tab where a page has one (personas,
  playbooks, system prompt templates). The status bar link now reads "View
  changes and test cases", and activating a version in review goes through the
  test report: one click if every test case passed or there are none,
  otherwise the dialog that asks for a reason (part B). External tools have no
  diff endpoint, so on their page the test report only takes effect through
  that dialog.
