- The German UI now calls the version status `review` "Zur Freigabe" instead
  of "In Review": status badge, status bar, detail-page notes and banners
  ("liegt zur Freigabe", "wartet auf Freigabe"), the dashboard activity line
  ("reichte zur Freigabe ein"), the auto-save conflict message and the agent
  policy preset description. "Review" is now reserved for the conversation
  about an agent (Phase E, A4a). Buttons and toasts follow as well ("Zur
  Freigabe einreichen", "Zur Freigabe eingereicht.", "Freigabe abgelehnt."),
  as does the system-prompt capability label. The version graph
  (`BranchStatus`) shows the translated status label instead of the raw API
  value ("v3 Zur Freigabe" instead of "v3 review"). Only German texts change;
  English, i18n keys and the API stay as they are.
