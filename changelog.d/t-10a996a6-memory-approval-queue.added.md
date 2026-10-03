- New "Memory" page with the "Awaiting approval" queue (learning loop C5a,
  memory management spec S1′).

  The navigation gains "Memory" under "Operations". `/memory` opens the
  workspace-wide approval queue: held-back entries first (one by one, with the
  reason and no checkbox), then "Your user memory" and one block per agent with
  "Approve all N from <agent>" (confirmation dialog; if the count changed in
  the meantime, the dialog shows the new number and asks again). Change and
  deletion proposals show a word diff and are decided one by one. Selection
  (up to 100) can be approved or rejected in one step; entries that fail stay
  selected and show the reason on their row. Search and the agent filter are
  kept in the URL. Viewers see only their own user memory; another member's
  user memory is never shown. Learning suggestions do not appear in the queue.
