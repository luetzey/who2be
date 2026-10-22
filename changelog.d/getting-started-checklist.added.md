- Dashboard: a "Getting started" checklist at the top (onboarding P3), rendered
  from every tutorial marked `welcome: true` — step definitions and progress
  come from `GET /v1/me/tutorials`, titles and text from the tutorial's
  Markdown, so no step is hard-coded. The next open step is expanded; each
  step offers the action that fits its type (go to Agents for steps Who2Be
  detects itself, open the page, mark as done) plus "Skip". "Hide" skips all
  open steps through the existing PATCH (no API change); "Restart" on the
  tutorial page brings the list back. Once every step is really done, a
  "You're all set" card stays for 7 days. Viewers do not see the agent steps.
  The list reloads when the tab regains focus. The tutorial hook and the
  Markdown renderer moved out of the help pages into
  `features/help/hooks/useTutorials.ts` and
  `features/help/components/HelpMarkdown.tsx`; the dashboard imports only via
  `features/help/index.ts`, so its chunk does not include the help pages.
