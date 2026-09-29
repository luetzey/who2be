- Test cases can now be managed in the web app (learning loop B4, design spec S10).

  New components `TestCaseList` and `TestCaseForm` list the test cases of an
  agent or an element (persona, playbook, system prompt), create new ones and
  archive them after a confirmation. Test case content is immutable (ADR-0053
  3.2): instead of "edit" there is "Create new revision", which creates a new
  test case with `supersedes_id` and archives the old one. Archived test cases
  stay visible via "Show archived". Viewers see a permissions notice instead of
  the list. The web client gains `listTestCases`, `getTestCase`,
  `createTestCase` and `retireTestCase`. The tab entry on the detail pages
  follows in a separate change.
