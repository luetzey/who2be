- CI: pull requests that change user-facing web components or existing UI
  text without touching the in-app help now get a warning (annotation and a
  line in the job summary of `changes`). A line `Hilfe: n/a – <reason>` in the
  PR description with a reason from a fixed list (`intern`, `kein UI-Text`,
  `nur Tests`, `Folgekarte <id>`) silences it. The pull request template has
  the new `Hilfe:` line. It is a warning, not a required check.
