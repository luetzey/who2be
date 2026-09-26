- The Hetzner deploy script now verifies the single-writer operating limit
  instead of relying on Compose's recreate order: after `up -d --wait` it
  asserts that exactly one `api` container is running and aborts with exit
  code 3 otherwise. Table-store rows live in one SQLite file per work area
  (ADR-0049) and tolerate exactly one writing process, so a second instance
  corrupts data without raising an error — the in-process start guard cannot
  see beyond its own process tree.

  Compose itself does not create such an overlap: `recreateContainer` creates
  the new container, *then* stops the old one, and only starts the new one in
  the following phase (verified in Compose v2.20, v2.29 and v2.39); an overlap
  would require `deploy.update_config.order: start-first`, whose default is
  `stop-first`. What the analysis cannot cover is that the Compose version
  installed on the host is not pinned. An explicit `stop` before `up` would
  close that remaining assumption completely — with the old container already
  stopped, no recreate order can produce two running ones — but it costs a full
  start plus health-check grace period of downtime on every deploy, so it was
  deliberately not added: the sequence is verified across v2.20–v2.39 and the
  drift tests reject `update_config`/`start-first`. The assertion is not a
  substitute for it: running after `--wait`, it measures the end state, so it
  guards against *persistent* second instances (an orphan from an earlier
  bringup, a manually started one, an `api` container that never came up)
  rather than a transient recreate window.

  The drift tests now cover every Compose file that defines an `api` service
  (previously two of eight — the cloud overlays were unguarded) and reject
  `update_config`/`start-first` alongside `replicas`, `scale` and `--workers`.
  The count check itself is exercised against a stubbed `compose ps`, so it is
  verified — not merely asserted in prose — that only container IDs are counted
  and diagnostic output on stderr is not. The operating limit is documented in
  the Hetzner runbook, including the recovery path when the assertion fires.
