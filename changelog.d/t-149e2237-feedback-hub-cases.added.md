- The feedback hub now has URL-synced tabs and a case list (learning loop
  D6b, ADR-0053).

  `?tab=` selects the tab and is updated with `replace`. "Cases"
  (`?tab=cases`) is the new default; the former "Inbox" is now "Building
  blocks" (`?tab=signals`) and shows the unchanged feedback inbox; "Curation"
  stays. Unknown tabs, or tabs the role may not see, fall back to "Cases".
  Viewers see only "My cases", without a tab bar. The page header gets the
  brand "Report a case" button (opens the case dialog without a preset
  agent) next to the outline "Report a problem".

  The case list uses the shared filter bar: status chips with counts from
  `GET /cases/counts` ("Open" covers `open` and `reopened` and filters
  server-side with both values), plus filters for agent and "Assigned to"
  (editors only). Filters live in the URL. Each row links to
  `/w/:ws/feedback/cases/:id` and shows the agent, status, the expected
  behaviour, the situation and source, date and kind ("Blocked" only for high
  severity). Pagination uses the cursor with "Load more". Loading, empty
  (open, filtered, viewer) and error states are covered.
