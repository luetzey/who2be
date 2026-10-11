- Privacy: Deleting an account now also removes the user's ID from the
  `target` and `detail` of audit log entries in workspaces that continue to
  exist (account deletion requested, role changed, member removed, user memory
  purged). The ID is replaced by the anonymous placeholder, so the action and
  its count remain visible. Previously only the acting user was anonymized.
