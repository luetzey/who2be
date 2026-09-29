- The English interface no longer shows German text in the system prompt
  detail page, the tool detail page, the dashboard activity feed and the
  playbook form.

  The system prompt review banner ("Version v2 is in review"), its "Versions"
  tab, the restore toast and the tab list label on system prompt and tool
  detail pages now come from the locale files. Dashboard activity entries
  ("Alice submitted for review Persona Coach") use the existing
  `dashboard.activity.*` keys instead of hard-coded German verbs, and the
  playbook form's type field reads "Type" in English. A test renders each of
  these places in English, and another one fails if `en.json` contains
  German umlauts.
