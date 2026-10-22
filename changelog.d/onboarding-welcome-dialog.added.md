- Web: a welcome dialog greets new users on the dashboard of their own personal
  workspace (onboarding P6). It opens once — `welcome_seen` is recorded on
  open, so a reload does not bring it back — and never on top of the cookie
  notice; it waits until the notice is acknowledged. The dialog connects the
  Builder in one step ("Connect with Claude", Claude Code, Cursor/VS Code or
  another app, sharing the texts and links of the agent page's connect block),
  waits for the first MCP call (every 5 s and on returning to the tab, at most
  10 minutes, "Yes, continue" after 2 minutes) and then shows a short success
  animation. Users who join a team workspace by invitation only get the
  checklist. "Restart introduction" in the help menu opens it again. Escape,
  ✕ and "Skip" close it; a click on the backdrop does not. Below 768 px it is
  full screen. Animations run once, stay under 5 s and show their end state
  immediately under "reduce motion".
