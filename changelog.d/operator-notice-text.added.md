- Operators can now set free-text notices per language at runtime, without a rebuild.

  `WHO2BE_LAUNCH_MESSAGE_DE` / `_EN` replaces the fixed text of the "coming
  soon" page. The same page now also appears when GoTrue rejects a Google,
  GitHub or Apple sign-in because sign-up is disabled (`signup_disabled`),
  instead of the raw "Signups not allowed for this instance" error.
  `WHO2BE_NOTICE_DE` / `_EN` with `WHO2BE_NOTICE_LEVEL` (`info` or `warning`)
  shows a banner on the sign-in page and at the top of the app, for example
  before maintenance; signed-in users can dismiss it for the browser session.
  All texts render as plain text, are capped at 500 characters and are
  written JSON-safe into `/config.js`. See `docs/signup-and-invites.md`.
