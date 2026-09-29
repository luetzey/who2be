- Web UI: system prompts in review now get the same "View changes" link in
  their status bar as personas, playbooks and resources. It opens the
  "Versions" tab with the diff of the review version already expanded. The
  system-prompt detail page reads `?tab=<tab>` and `?diff=<version>` from the
  URL, so `/system-prompts/<id>?tab=versions&diff=2` opens the diff directly.
  Unknown tabs and invalid versions are ignored (Audit E1-A).
