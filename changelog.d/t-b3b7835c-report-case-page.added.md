- Web: below `md`, "Report a case" opens its own full-screen page at
  `/w/:workspace/feedback/cases/new` instead of the dialog (ADR-0053 D6c′,
  delta spec S6 "390 px"). From an agent the agent is fixed
  (`?agent=<id>`); from the feedback hub it is picked on the page. The button
  bar stays pinned to the bottom. Back, Cancel and a successful report return
  to where the page was opened, including its filters; a direct link without
  that origin falls back to the case list. Unsaved input still asks
  "Discard your input?" first. From `md` up the dialog stays.
- Web: the case list in the feedback hub reloads after a case was reported, and
  while the workspace role is still loading the hub shows a placeholder instead
  of briefly rendering the viewer variant ("My cases").
