- Web UI: the "View changes" link from the review status bar and the
  `?tab=versions&diff=<version>` deep link now also work on playbook and
  resource detail pages. On the playbook page, whose tab panels stay mounted,
  a `diff` parameter without `tab=versions` is ignored so no hidden diff is
  loaded (Audit E1-A).
