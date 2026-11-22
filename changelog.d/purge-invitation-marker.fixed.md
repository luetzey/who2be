- The purge run no longer aborts when a workspace holds two or more expired,
  never-accepted invitations. Redacting their e-mail addresses to the shared
  marker `<redacted>` collided in the partial unique index on open invitations
  (expired rows are neither accepted nor revoked, so they stay in it), and the
  `UniqueViolationError` stopped `purge_expired` before any later cleanup step.
  The marker is now unique per row (`<redacted>:<id>`); rows already redacted
  with the old marker are left as they are, and `revoked_at` is not touched.
