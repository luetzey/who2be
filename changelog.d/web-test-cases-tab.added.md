- Test cases are now reachable from the detail pages (learning loop B4b,
  design spec S10).

  Persona, playbook and system prompt detail pages gain a "Test cases" tab
  (no counter, spec §2.3), placed before "Versions" and deep-linkable via
  `?tab=tests`. It lists the test cases bound directly to that element; test
  cases that affect an element through an agent follow once version IDs are
  readable. The agent detail page gains a collapsible "Test cases" section at
  the end, opened directly by `#tests` or `?tab=tests`; the tabbed agent page
  from spec §2.3 is a separate change. The list only loads when the tab or
  section is opened.
