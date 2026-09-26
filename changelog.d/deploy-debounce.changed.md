- A series of merges to `main` now produces **one** deployment instead of one
  per push. Previously every push started its own run: on 2026-09-23 at 20:05
  that was nine runs within 36 seconds — nine image build rounds and nine
  service restarts, eight of which were worthless because only the last state
  counts.

  The `deploy` workflow gained a `debounce` job that, on a push, waits
  `DEPLOY_DEBOUNCE_SECONDS` (10 minutes) behind a concurrency group with
  `cancel-in-progress: true`. Every further push to `main` cancels the waiting
  run and opens its own window, so after the last merge of a series exactly one
  run survives and deploys the newest state. The window is 10 rather than 30
  minutes as a latency decision, not because 30 would bundle nothing: measured
  over the last 100 push runs (2026-08-22…2026-09-24), a 10-minute window
  yields 59 deployments and a 30-minute window 49 — ten fewer over a month
  (~17 %), at the price of up to 30 instead of 10 minutes to live on *every*
  merge. The dense series that prompted this change are already fully covered
  at 10 minutes: the largest gap between *consecutive* runs of the four series
  on 2026-09-23/24 was 3 min 35 s, and across all 100 measured runs the largest
  gap below the threshold is 6.5 minutes.
  Waiting is free here: the repository is public and runs standard runners, for
  which GitHub bills no Actions minutes.

  No state is left undelivered by the bundling itself. A run is only ever
  cancelled because a *newer* run for the same branch exists, and that newer
  run carries a commit containing the cancelled one. The `deploy` job itself is
  serialized (`cancel-in-progress: false`) and therefore never aborted
  mid-deployment; a merge arriving while it runs becomes `pending` and ships
  right after. One pre-existing caveat is unchanged by this work: a commit
  whose message contains `[skip ci]` starts no workflow run at all, so such a
  state is not deployed until the next regular push — that was already true
  before.

  Two consequences worth knowing: a merge is live up to 10 minutes later, and
  the skipped intermediate commits are never built, so GHCR holds no image for
  them. `workflow_dispatch` still deploys immediately, without any window.

- The `deploy` job is now bound to `main` (`github.ref == 'refs/heads/main'`).
  `workflow_dispatch` can be triggered from any ref, and a production
  deployment from a test branch was an open flank. Building images from a
  branch remains possible.
