- The "Memory" page can pull back automatic approvals, and the memory card on
  an agent's page opens the detail sheet (learning loop C5c-2, memory
  management spec §8).

  Editors and admins find "Pull back automatic approvals…" under "More
  actions" in the page header; `?pullback=1` opens the same dialog. It picks a
  period (last 24 hours, last 7 days, or since a date up to 90 days back) and
  a scope (all agents, or one agent), counts the affected entries first and
  shows up to five of them, and only then pulls back exactly the confirmed
  number. If the number changed in the meantime, the dialog stays open with
  the new number and asks again instead of retrying on its own. Entries go
  back to "Awaiting approval"; nothing is deleted. Editors cover agent memory
  and their own user memory; admins also cover other members' user memory,
  which they only see as a count, never as content. Viewers don't see the
  action.

  On an agent's page, the chevron on each memory entry now opens the same
  detail sheet with history and rollback as on the "Memory" page, also as a
  deep link via `?entry=<id>`.
