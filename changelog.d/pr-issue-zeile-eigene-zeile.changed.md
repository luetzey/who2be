- The issue reference in a pull request is now a line of its own at the top of
  the body, starting with `Issue:` (`Issue: Closes #NNN`, `Issue: Refs #NNN`
  or `Issue: n/a (Kanban card <id>, <context>)`). The PR template used to offer
  the three cases as bullets under a heading, which led to the line being
  embedded in a bullet or a sentence; review checks for `^Issue:` and blocked
  three pull requests for it (#854, #856, #863). Template and
  `CONTRIBUTING.md` §Issue reference now name the exact form and the
  self-check command.
