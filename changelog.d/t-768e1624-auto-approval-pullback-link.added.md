- The "Automatic approval" setting links to the pull-back dialog on the
  "Memory" page, and the list of what automatic approval doesn't catch now
  says that everything approved automatically can be pulled back in one go
  (learning loop C6b, memory management spec §11.1, rows S4 and S4a).

  Admins find "Pull back automatic approvals…" below the approval matrix in
  Settings → Workspace; it opens `/memory?pullback=1` in the current
  workspace. The sentence "You can pull back everything approved
  automatically in one go." appears both in the confirmation dialog shown
  before a cell is turned on and in the permanent list in the section. It
  ships only now because the promise needs the pull-back dialog to exist
  (ADR-0053 6.4.1). The "last 7 days" figure planned for the same section
  follows separately: it needs a server-side count of automatically approved
  entries that the API does not offer yet.
