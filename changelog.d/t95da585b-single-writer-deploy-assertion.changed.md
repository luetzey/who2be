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
  `stop-first`. The assertion covers what the analysis cannot: the Compose
  version installed on the host is not pinned. No explicit `stop` before `up`
  was added — it would lengthen downtime by a full start plus health-check
  grace period without addressing that remaining assumption.

  The drift tests now cover every Compose file that defines an `api` service
  (previously two of eight — the cloud overlays were unguarded) and reject
  `update_config`/`start-first` alongside `replicas`, `scale` and `--workers`.
  The operating limit is documented in the Hetzner runbook, including the
  recovery path when the assertion fires.
