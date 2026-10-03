- Memory entries open in a detail sheet with history and rollback
  (learning loop C5c-1, memory management spec S3′).

  On the "Memory" page, the chevron on an entry row and "History" on an
  expanded row in "Awaiting approval" open a sheet via `?entry=<id>`; the link
  works as a deep link too. The sheet shows the fact and its state, the
  provenance with the channel set by the server kept apart from the origin
  according to the agent, the delivery count, and the history newest first.
  Each history step names who did it (a member, an agent, or "Automatic") and
  shows the word diff of the fact. "Restore the state before this change" asks
  for confirmation with a preview including a status change and extends the
  history instead of rewinding it. The actions follow the state: approve or
  reject a proposal, confirm an unconfirmed entry, reactivate an expired one,
  edit the fact, and delete the entry together with its history. Your own user
  memory can be managed from viewer up, agent memory from editor up. Another
  member's user memory never opens, not even through a deep link.
