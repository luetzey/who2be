- `audit_log` entries are anonymized when their workspace or organization is
  deleted (migration 0106). The action, the timestamp and the scope stay; the
  actor becomes the anonymized sentinel, the target is cleared and `detail`
  keeps only the keys on a per-action allowlist (roles, deadlines, counts).
  Before, the rows outlived the deletion unchanged. The trigger also fires on
  the API workspace delete under the app role, which still cannot update
  `audit_log` itself. Rows from scopes deleted before 0106 are anonymized by
  the migration. Deleting the anonymized rest after 12 months follows as a
  separate worker routine.
