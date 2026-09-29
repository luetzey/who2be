- Web UI: "Set up two-factor" in the status bar now remembers where you came
  from. Once the second factor is verified on the account page, you are taken
  straight back to that page, including an open diff
  (`/settings/account?returnTo=<path>`). Only paths inside the app are
  accepted. External URLs, protocol-relative and backslash paths,
  `javascript:` and control characters are ignored. The same rule now also
  guards `next` after login (Audit A1, E5-A).
