- Web UI: publishing no longer fails without warning when the session lacks a
  second factor. If the session is only single-factor (`aal1`), the status bar
  shows "Publishing requires two-factor sign-in." with a "Set up two-factor"
  link to account settings instead of an active "Publish"/"Activate" button.
  The server-side MFA requirement (ADR-0023) is unchanged; the UI only
  announces it. The `mfa_required` error is now translated, so English users no
  longer get a German toast. "Back to draft" in review is no longer styled as
  a destructive action (Audit A1, A2).
