- The "Memory" page gains an "Entries" tab: the full list of what each agent
  remembers (learning loop C5b-1, memory management spec S2′).

  `/memory?tab=entries` lists every agent-bound entry, newest first by
  default, with cursor-based "Load more". The facets agent, kind, status,
  health, origin according to the agent, and channel all show their counts
  from the server and are stored in the URL. Below 1024 px they move into a
  filter sheet. Each row shows one action that fits its state: "Confirm" for
  unconfirmed entries and "Reactivate" for expired ones. Held-back proposals
  (from a web page, file or tool, inferred, or instructions) cannot be
  approved from this list; their row links to "Awaiting approval", where they
  are decided one by one with the reason shown. A selection of up to
  100 entries can be confirmed, approved, rejected or deleted in one step;
  entries that do not fit the action are skipped, and failures stay selected
  with the reason on their row. "Confirm all N" confirms every unconfirmed
  entry that matches the current filters and asks again if the count changed
  in the meantime. Viewers do not see the tab, and another member's user
  memory never appears in the list.
