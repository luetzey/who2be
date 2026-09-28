- Web UI: from a persona in review, the status bar now has a "View changes"
  link that opens the "Versions" tab with the diff of the review version
  already expanded — one click instead of switching tabs and finding the row.
  The persona detail page reads `?tab=<tab>` and `?diff=<version>` from the
  URL, so a link like `/personas/<id>?tab=versions&diff=2` opens the diff
  directly; unknown tabs and invalid or non-existent versions are ignored.
  Playbook, resource and system-prompt detail pages follow in a separate
  change (Audit E1-A).
